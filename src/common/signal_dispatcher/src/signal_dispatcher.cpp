#include <signal_dispatcher.hpp>


namespace signal_dispatcher
{
    SignalDispatcher& SignalDispatcher::GetInstance() {
        static SignalDispatcher instance;
        return instance;
    }

    boost::signals2::connection SignalDispatcher::RegisterListener(const std::string& event, const SignalType::slot_type& slot) {
        return signals[event].connect(slot);
    }

    void SignalDispatcher::Notify(const std::string& event) {
        auto it = signals.find(event);
        if (it != signals.end()) {
            it->second();
        }
    }
} // namespace signal_dispatcher
