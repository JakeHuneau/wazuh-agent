cmake_minimum_required(VERSION 3.22)

set(CMAKE_TOOLCHAIN_FILE "${CMAKE_SOURCE_DIR}/../../vcpkg/scripts/buildsystems/vcpkg.cmake")
set(VCPKG_MANIFEST_DIR ${CMAKE_SOURCE_DIR}/../../)

project(SignalDispatcher)

include(../../cmake/CommonSettings.cmake)
set_common_settings()

find_package(Boost REQUIRED COMPONENTS signals2)

add_library(SignalDispatcher src/signal_dispatcher.cpp)
target_include_directories(SignalDispatcher PUBLIC include)
target_link_libraries(SignalDispatcher PUBLIC Boost::signals2)

include(../../cmake/ConfigureTarget.cmake)
configure_target(SignalDispatcher)

if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()
