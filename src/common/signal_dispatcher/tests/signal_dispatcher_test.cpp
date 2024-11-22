#include <gtest/gtest.h>
#include <signal_dispatcher.hpp>
#include <string>
#include <vector>

using namespace signal_dispatcher;

/// @brief Test suite for the SignalDispatcher class.
class SignalDispatcherTest : public ::testing::Test {
protected:
    /// @brief Reset state before each test.
    void SetUp() override {
        // Perform any setup operations before each test.
    }

    /// @brief Cleanup after each test.
    void TearDown() override {
        // Perform any cleanup operations after each test.
    }
};

/// @test Test singleton instance retrieval.
TEST_F(SignalDispatcherTest, GetInstanceReturnsSameInstance) {
    SignalDispatcher& instance1 = SignalDispatcher::GetInstance();
    SignalDispatcher& instance2 = SignalDispatcher::GetInstance();

    EXPECT_EQ(&instance1, &instance2) << "SignalDispatcher::GetInstance should return the same instance.";
}

/// @test Test registering and notifying listeners.
TEST_F(SignalDispatcherTest, RegisterListenerAndNotify) {
    SignalDispatcher& dispatcher = SignalDispatcher::GetInstance();
    std::string triggeredEvent;

    // Register a listener for the "test_event".
    dispatcher.RegisterListener("test_event", [&]() { triggeredEvent = "test_event"; });

    // Notify the "test_event".
    dispatcher.Notify("test_event");

    // Check if the listener was triggered.
    EXPECT_EQ(triggeredEvent, "test_event") << "Listener for 'test_event' should have been triggered.";
}

/// @test Test notifying an event with no listeners.
TEST_F(SignalDispatcherTest, NotifyWithoutListeners) {
    SignalDispatcher& dispatcher = SignalDispatcher::GetInstance();

    // Notify an event that has no listeners.
    EXPECT_NO_THROW(dispatcher.Notify("unregistered_event")) << "Notifying an unregistered event should not throw.";
}

/// @test Test multiple listeners for the same event.
TEST_F(SignalDispatcherTest, MultipleListenersForSameEvent) {
    SignalDispatcher& dispatcher = SignalDispatcher::GetInstance();
    std::vector<std::string> notifications;

    // Register multiple listeners for the same event.
    dispatcher.RegisterListener("shared_event", [&]() { notifications.emplace_back("listener1"); });
    dispatcher.RegisterListener("shared_event", [&]() { notifications.emplace_back("listener2"); });

    // Notify the event.
    dispatcher.Notify("shared_event");

    // Check if both listeners were triggered.
    ASSERT_EQ(notifications.size(), 2) << "Both listeners should have been triggered.";
    EXPECT_EQ(notifications[0], "listener1");
    EXPECT_EQ(notifications[1], "listener2");
}

