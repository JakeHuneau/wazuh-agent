#pragma ocne

#include "db_wrapper.hpp"

#include <sqlite3.h>
#include <iostream>

static const char* sqlitedb_path = "sqlite3_events.db";

class SQLiteWrapper : public DBWrapper<sqlite3> {
public:
    SQLiteWrapper() {
        if (sqlite3_open(sqlitedb_path, &db)) {
            std::cerr << "Can't open database: " << sqlite3_errmsg(db) << std::endl;
            db = nullptr;
        }
    }

    ~SQLiteWrapper() override {
        if (db) {
            sqlite3_close(db);
        }
    }

    void createTable() override {
        const char* sql = "CREATE TABLE IF NOT EXISTS events ("
                          "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                          "event_data TEXT NOT NULL, "
                          "event_type TEXT NOT NULL, "
                          "timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, "
                          "status TEXT DEFAULT 'pending'"
                          ");";
        char* errMsg = nullptr;
        int rc = sqlite3_exec(db, sql, nullptr, nullptr, &errMsg);
        if (rc != SQLITE_OK) {
            std::cerr << "Error creating table: " << errMsg << std::endl;
            sqlite3_free(errMsg);
        }
    }

    void insertEvent(int id, const std::string& event_data, const std::string& event_type) override {
        const char* sql = "INSERT INTO events (event_data, event_type) VALUES (?, ?);";
        sqlite3_stmt* stmt;
        sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr);
        sqlite3_bind_text(stmt, 1, event_data.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 2, event_type.c_str(), -1, SQLITE_STATIC);
        sqlite3_step(stmt);
        sqlite3_finalize(stmt);
    }

    std::vector<Event> fetchPendingEvents(int limit) override {
        const char* sql = "SELECT id, event_data FROM events WHERE status = 'pending' LIMIT ?;";
        sqlite3_stmt* stmt;
        sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr);
        sqlite3_bind_int(stmt, 1, limit);

        std::vector<Event> events;
        while (sqlite3_step(stmt) == SQLITE_ROW) {
            int id = sqlite3_column_int(stmt, 0);
            const unsigned char* event_data = sqlite3_column_text(stmt, 1);
            events.emplace_back(Event{id, std::string(reinterpret_cast<const char*>(event_data)), "", "pending"});
        }
        sqlite3_finalize(stmt);
        return events;
    }

    void updateEventStatus(const std::vector<int>& event_ids) override {
        const char* sql = "UPDATE events SET status = 'dispatched' WHERE id = ?;";
        sqlite3_stmt* stmt;
        sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr);

        for (int id : event_ids) {
            sqlite3_bind_int(stmt, 1, id);
            sqlite3_step(stmt);
            sqlite3_reset(stmt);
        }
        sqlite3_finalize(stmt);
    }

private:
    sqlite3* db = nullptr;
};