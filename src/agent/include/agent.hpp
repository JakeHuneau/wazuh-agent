#pragma once

#include <agent_info.hpp>
#include <communicator.hpp>
#include <configuration_parser.hpp>
#include <task_manager.hpp>

#include <queue>
#include <string>

class Agent
{
public:
    Agent();
    ~Agent();

private:
    std::queue<std::string> m_messageQueue;

    TaskManager m_taskManager;
    AgentInfo m_agentInfo;
    configuration::ConfigurationParser m_configurationParser;
    communicator::Communicator m_communicator;
};
