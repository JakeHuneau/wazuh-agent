find_package(GTest CONFIG REQUIRED)

add_executable(SignalDispatcher_test signal_dispatcher_test.cpp)
configure_target(SignalDispatcher_test)
target_link_libraries(SignalDispatcher_test PUBLIC SignalDispatcher Config GTest::gtest GTest::gtest_main GTest::gmock GTest::gmock_main Boost::signals2)
add_test(NAME SignalDispatcherTest COMMAND SignalDispatcher_test)
