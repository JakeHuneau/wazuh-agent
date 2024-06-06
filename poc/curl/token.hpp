#pragma once

#include <boost/beast/core.hpp>
#include <jwt-cpp/jwt.h>

#include <string>
#include <unordered_map>
#include <chrono>
#include <ctime>

const std::string uuidKey = "uuid=";
const std::string tokenKey = "token=";
const std::string eventKey = "event=";
const std::string passwordKey = "password=";
const std::string bearerPrefix = "Bearer ";

void fail(boost::beast::error_code ec, char const* what) {
    std::cerr << what << ": " << ec.message() << "\n";
}

struct TokenInfo {
    std::string token;
    std::time_t expiry;
};

std::unordered_map<std::string, TokenInfo> validTokens;

std::string generateToken() {
    std::string token = "new_token";
    return token;
}

bool verifyPassword(const std::string& uuid, const std::string& password) {
    return true;
}

std::string createToken() {
    auto token = jwt::create()
        .set_issuer("some-auth-server")
        .set_type("JWS")
        .set_payload_claim("sample", jwt::claim(std::string("test")))
        .sign(jwt::algorithm::hs256{"your-secret-key"});

    return token;
}

bool verifyToken(const std::string& token) {
    try {
        auto decoded = jwt::decode(token);

        auto verifier = jwt::verify()
            .allow_algorithm(jwt::algorithm::hs256{"your-secret-key"})
            .with_issuer("some-auth-server");

        verifier.verify(decoded);

        return true;
    } catch (const std::exception& e) {
        std::cerr << "Token verification failed: " << e.what() << std::endl;
        return false;
    }
}