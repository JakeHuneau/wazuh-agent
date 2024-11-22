#pragma once

#include <boost/signals2.hpp>
#include <string>
#include <unordered_map>

namespace signal_dispatcher
{
    /// @brief Manages event-driven communication through signals and listeners.
    ///
    /// The SignalDispatcher class is a singleton that provides a mechanism to register listeners
    /// (callbacks) for specific events and notify those listeners when the events occur.
    /// It uses the Boost.Signals2 library for implementing the signal-slot pattern.
    class SignalDispatcher {
    public:
        /// @brief Defines the type of signal used for event notifications.
        using SignalType = boost::signals2::signal<void()>;

        /// @brief Retrieves the singleton instance of the SignalDispatcher.
        ///
        /// This function ensures that there is a single instance of the SignalDispatcher
        /// throughout the application's lifetime.
        ///
        /// @return A reference to the singleton instance of the SignalDispatcher.
        static SignalDispatcher& GetInstance();

        /// @brief Registers a listener for a specific event.
        ///
        /// This function associates a callback function with a named event. When the event occurs,
        /// all registered listeners for that event will be notified.
        ///
        /// @param event The name of the event to listen for.
        /// @param slot The callback function (slot) to execute when the event is notified.
        /// @return A boost::signals2::connection object that can be used to manage the listener's lifecycle.
        boost::signals2::connection RegisterListener(const std::string& event, const SignalType::slot_type& slot);

        /// @brief Notifies all listeners registered for a specific event.
        ///
        /// This function triggers all the callbacks (slots) associated with the given event.
        /// If no listeners are registered for the event, this function does nothing.
        ///
        /// @param event The name of the event to notify.
        void Notify(const std::string& event);

    private:
        /// @brief Private constructor to enforce the singleton pattern.
        SignalDispatcher() = default;

        /// @brief Stores signals for each registered event.
        ///
        /// The key is the event name, and the value is the corresponding Boost.Signal object
        /// that manages the callbacks (slots) for the event.
        std::unordered_map<std::string, SignalType> signals = {};
    };
} // namespace signal_dispatcher
