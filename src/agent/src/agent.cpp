#include <agent.hpp>

#include <command_handler_utils.hpp>
#include <http_client.hpp>
#include <message.hpp>
#include <message_queue_utils.hpp>
#include <module_command/command_entry.hpp>

#include <filesystem>
#include <memory>
#include <thread>

constexpr int A_SECOND_IN_MILLIS = 1000;

Agent::Agent(const std::string& configFile, std::unique_ptr<ISignalHandler> signalHandler)
    : m_agentInfo([this]() { return m_sysInfo.os(); }, [this]() { return m_sysInfo.networks(); })
    , m_messageQueue(std::make_shared<MultiTypeQueue>())
    , m_signalHandler(std::move(signalHandler))
    , m_configurationParser(configFile.empty() ? configuration::ConfigurationParser()
                                               : configuration::ConfigurationParser(std::filesystem::path(configFile)))
    , m_communicator(
          std::make_unique<http_client::HttpClient>(),
          m_agentInfo.GetUUID(),
          m_agentInfo.GetKey(),
          [this]() { return m_agentInfo.GetHeaderInfo(); },
          [this]<typename T>(std::string table, std::string key) -> std::optional<T>
          { return m_configurationParser.GetConfig<T>(std::move(table), std::move(key)); })
    , m_moduleManager([this](Message message) -> int { return m_messageQueue->push(std::move(message)); },
                      m_configurationParser,
                      [this](std::function<void()> task) { m_taskManager.EnqueueTask(std::move(task)); })
{
    m_maxBatchingSize = m_configurationParser.GetConfig<int>("agent", "max_batching_size")
                            .value_or(config::agent::DEFAULT_MAX_BATCHING_SIZE);

    if (m_maxBatchingSize < A_SECOND_IN_MILLIS) {
        LogWarn("max_batching_size cannot be lower than 1s. Using default value.");
        m_maxBatchingSize = config::agent::DEFAULT_MAX_BATCHING_SIZE;
    }
    m_centralizedConfiguration.SetGroupIdFunction([this](const std::vector<std::string>& groups)
                                                  { return m_agentInfo.SetGroups(groups); });

    m_centralizedConfiguration.GetGroupIdFunction([this]() { return m_agentInfo.GetGroups(); });

    m_centralizedConfiguration.SetDownloadGroupFilesFunction(
        [this](const std::string& groupId, const std::string& destinationPath)
        { return m_communicator.GetGroupConfigurationFromManager(groupId, destinationPath); });

    m_taskManager.Start(std::thread::hardware_concurrency());
}

Agent::~Agent()
{
    m_taskManager.Stop();
}

void Agent::Run()
{
    m_taskManager.EnqueueTask(m_communicator.WaitForTokenExpirationAndAuthenticate());

    m_taskManager.EnqueueTask(m_communicator.GetCommandsFromManager(
        [this](const std::string& response) { PushCommandsToQueue(m_messageQueue, response); }));

    m_taskManager.EnqueueTask(m_communicator.StatefulMessageProcessingTask(
        [this]()
        {
            return GetMessagesFromQueue(
                m_messageQueue, MessageType::STATEFUL, m_maxBatchingSize, [this]() { return m_agentInfo.GetMetadataInfo(false); });
        },
        [this]([[maybe_unused]] const std::string& response)
        { PopMessagesFromQueue(m_messageQueue, MessageType::STATEFUL, m_maxBatchingSize); }));

    m_taskManager.EnqueueTask(m_communicator.StatelessMessageProcessingTask(
        [this]()
        {
            return GetMessagesFromQueue(
                m_messageQueue, MessageType::STATELESS, m_maxBatchingSize, [this]() { return m_agentInfo.GetMetadataInfo(false); });
        },
        [this]([[maybe_unused]] const std::string& response)
        { PopMessagesFromQueue(m_messageQueue, MessageType::STATELESS, m_maxBatchingSize); }));

    m_moduleManager.AddModules();
    m_taskManager.EnqueueTask([this]() { m_moduleManager.Start(); });

    m_taskManager.EnqueueTask(m_commandHandler.CommandsProcessingTask<module_command::CommandEntry>(
        [this]() { return GetCommandFromQueue(m_messageQueue); },
        [this]() { return PopCommandFromQueue(m_messageQueue); },
        [this](module_command::CommandEntry& cmd)
        {
            if (cmd.Module == "CentralizedConfiguration")
            {
                return DispatchCommand(
                    cmd,
                    [this](std::string command, nlohmann::json parameters)
                    { return m_centralizedConfiguration.ExecuteCommand(std::move(command), std::move(parameters)); },
                    m_messageQueue);
            }
            return DispatchCommand(cmd, m_moduleManager.GetModule(cmd.Module), m_messageQueue);
        }));

    m_signalHandler->WaitForSignal();
    m_moduleManager.Stop();
    m_communicator.Stop();
}
