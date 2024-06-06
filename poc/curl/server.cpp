#include <boost/asio/ip/tcp.hpp>
#include <string>
#include <unordered_map>
#include <chrono>
#include <ctime>

#include "server/listener.hpp"

namespace beast = boost::beast;
namespace http = beast::http;
namespace net = boost::asio;
using tcp = net::ip::tcp;


int main(int argc, char* argv[]) {
    auto const address = net::ip::make_address("0.0.0.0");
    auto const port = static_cast<unsigned short>(8080);

    net::io_context ioc{ 1 };

    std::make_shared<listener>(ioc, tcp::endpoint{ address, port })->run();

    ioc.run();

    return 0;
}