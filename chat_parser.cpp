#include <iostream>
#include <fstream>
#include <sstream>
#include <unordered_map>
#include <vector>
#include <string>
#include <algorithm>
#include <array>
#include <cstdio>
#include <utility>
#include <random>
#include <set>
#include <cctype>

// Define the Chat struct with fields matching the CSV columns
struct Chat {
    std::string id;
    std::string publisher_id;
    std::string user_id;
    std::string user_email;
    std::string visitor_id;
    std::string chat_id;
    std::string session_id;
    std::string url;
    std::string request_headers;
    std::string role;
    std::string text;
    std::string created_at;
};

// Define the Offer struct with fields matching the CSV columns
struct Offer {
    std::string offer_id;
    std::string name;
    std::string preview_url;
    std::string payout_type;       // "CPA" or "CPS"
    std::string payout_amount;     // raw string e.g. "$11.25"
    std::string payout_percentage; // raw string e.g. "80%"
    std::string click_to_run;
    // Derived fields
    std::vector<std::string> countries;  // extracted country codes (ISO 2-letter, normalized)
    bool all_countries = false;          // true if offer targets all countries
    double payout_amount_val = 0.0;     // numeric payout amount
    double payout_percentage_val = 0.0; // numeric payout percentage
};

// Define the AdSlot struct with fields matching ad-slots-3303.csv columns
struct AdSlot {
    std::string id;
    std::string visitor_id;
    std::string session_id;
    std::string chat_id;
    int assistant_message_count;
    int chat_history_length;
    int user_message_count;
    std::string geo_country_code;
    std::string created_at;
};

// Helper function to trim whitespace from strings
std::string trim(const std::string& str) {
    size_t start = str.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    size_t end = str.find_last_not_of(" \t\r\n");
    return str.substr(start, end - start + 1);
}

// Helper function to parse CSV line handling quoted fields
std::vector<std::string> parseCSVLine(const std::string& line) {
    std::vector<std::string> fields;
    std::string field;
    bool insideQuotes = false;

    for (size_t i = 0; i < line.length(); ++i) {
        char c = line[i];

        if (c == '"') {
            if (insideQuotes && i + 1 < line.length() && line[i + 1] == '"') {
                field += '"';
                ++i;
            } else {
                insideQuotes = !insideQuotes;
            }
        } else if (c == ',' && !insideQuotes) {
            fields.push_back(field);
            field.clear();
        } else {
            field += c;
        }
    }

    fields.push_back(field);
    return fields;
}

// Escape a string for use in a JSON string value
std::string jsonEscape(const std::string& s) {
    std::string result;
    result.reserve(s.size() + 16);
    for (char c : s) {
        switch (c) {
            case '"':  result += "\\\""; break;
            case '\\': result += "\\\\"; break;
            case '\n': result += "\\n";  break;
            case '\r': result += "\\r";  break;
            case '\t': result += "\\t";  break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    char buf[8];
                    snprintf(buf, sizeof(buf), "\\u%04x", (unsigned char)c);
                    result += buf;
                } else {
                    result += c;
                }
        }
    }
    return result;
}

// Execute a shell command and return its stdout
std::string execCommand(const std::string& cmd) {
    std::array<char, 8192> buffer;
    std::string result;
    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) {
        std::cerr << "Error: popen() failed!" << std::endl;
        return "";
    }
    while (fgets(buffer.data(), buffer.size(), pipe) != nullptr) {
        result += buffer.data();
    }
    pclose(pipe);
    return result;
}

// Extract a JSON string value for a given key from a JSON string (simple parser)
std::string extractJsonString(const std::string& json, const std::string& key) {
    std::string searchKey = "\"" + key + "\"";
    size_t keyPos = json.find(searchKey);
    if (keyPos == std::string::npos) return "";

    size_t colonPos = json.find(':', keyPos + searchKey.length());
    if (colonPos == std::string::npos) return "";

    size_t quoteStart = json.find('"', colonPos + 1);
    if (quoteStart == std::string::npos) return "";

    std::string value;
    for (size_t i = quoteStart + 1; i < json.length(); ++i) {
        if (json[i] == '\\' && i + 1 < json.length()) {
            if (json[i + 1] == '"') {
                value += '"';
                ++i;
            } else if (json[i + 1] == 'n') {
                value += '\n';
                ++i;
            } else if (json[i + 1] == '\\') {
                value += '\\';
                ++i;
            } else {
                value += json[i];
            }
        } else if (json[i] == '"') {
            break;
        } else {
            value += json[i];
        }
    }
    return value;
}

// ========== Country extraction from offer name ==========
// Splits name by " - " and looks for tokens that are 2-letter country codes
// or comma-separated lists of country codes (e.g. "US,CA")
// Also detects "All Countries" / "All Coutries" (typo in data)
// Normalizes UK -> GB to match ISO 3166-1 alpha-2 used in ad-slots
void extractCountries(Offer& offer) {
    const std::string& name = offer.name;

    // Check for "All Countries" or "All Coutries" (typo in data)
    std::string nameLower = name;
    std::transform(nameLower.begin(), nameLower.end(), nameLower.begin(), ::tolower);
    if (nameLower.find("all countries") != std::string::npos ||
        nameLower.find("all coutries") != std::string::npos) {
        offer.all_countries = true;
        return;
    }

    // Split name by " - "
    std::vector<std::string> parts;
    std::string delimiter = " - ";
    size_t start = 0;
    size_t end = name.find(delimiter);
    while (end != std::string::npos) {
        parts.push_back(name.substr(start, end - start));
        start = end + delimiter.length();
        end = name.find(delimiter, start);
    }
    parts.push_back(name.substr(start));

    // For each part, check if it looks like country codes
    // Country code tokens: 2 uppercase letters, possibly comma-separated
    // May have trailing qualifiers like "(Proof Needed)", "Android Only", "iOS Only"
    for (size_t i = 1; i < parts.size(); ++i) {
        std::string part = trim(parts[i]);

        // Remove known suffixes/qualifiers in parentheses or after " - "
        // e.g. "(Proof Needed)", "Android Only", "iOS Only", "V3"
        // We only care about the country code portion
        // Split by space and check the first token(s)
        std::string countryPart = part;

        // Remove anything in parentheses
        size_t parenPos = countryPart.find('(');
        if (parenPos != std::string::npos) {
            countryPart = countryPart.substr(0, parenPos);
        }
        countryPart = trim(countryPart);

        // Skip if empty
        if (countryPart.empty()) continue;

        // Check if this looks like comma-separated country codes
        // e.g. "US,CA" or just "US"
        // Also allow "US " with trailing space
        bool looksLikeCountryCodes = true;
        std::vector<std::string> codes;
        std::stringstream ss(countryPart);
        std::string token;
        while (std::getline(ss, token, ',')) {
            token = trim(token);
            if (token.empty()) continue;
            // A valid country code is 2 uppercase letters
            if (token.length() == 2 && std::isupper(token[0]) && std::isupper(token[1])) {
                codes.push_back(token);
            } else {
                looksLikeCountryCodes = false;
                break;
            }
        }

        if (looksLikeCountryCodes && !codes.empty()) {
            for (auto& code : codes) {
                // Normalize UK -> GB
                if (code == "UK") code = "GB";
                offer.countries.push_back(code);
            }
        }
    }
}

// ========== Parse payout amount ==========
// Strips currency symbols ($, EUR, £, etc.) and parses to double
double parsePayout(const std::string& raw) {
    std::string s = trim(raw);
    if (s.empty()) return 0.0;

    // Remove known currency prefixes
    const std::vector<std::string> prefixes = {"$", "EUR", "£", "€", "GBP", "CAD", "AUD"};
    for (const auto& prefix : prefixes) {
        if (s.substr(0, prefix.length()) == prefix) {
            s = s.substr(prefix.length());
            break;
        }
    }
    s = trim(s);

    try {
        return std::stod(s);
    } catch (...) {
        return 0.0;
    }
}

// ========== Parse payout percentage ==========
double parsePercentage(const std::string& raw) {
    std::string s = trim(raw);
    if (s.empty()) return 0.0;

    // Remove trailing %
    if (!s.empty() && s.back() == '%') {
        s.pop_back();
    }
    s = trim(s);

    try {
        return std::stod(s);
    } catch (...) {
        return 0.0;
    }
}

// ========== Filter offers by geo country code ==========
std::vector<Offer> filterOffersByGeo(const std::vector<Offer>& offers, const std::string& geoCountryCode) {
    std::vector<Offer> filtered;
    for (const auto& offer : offers) {
        // Include if offer targets all countries
        if (offer.all_countries) {
            filtered.push_back(offer);
            continue;
        }
        // Include if offer's country list contains the geo country code
        for (const auto& code : offer.countries) {
            if (code == geoCountryCode) {
                filtered.push_back(offer);
                break;
            }
        }
    }
    return filtered;
}

// ========== Group offers by payout type ==========
void groupByPayoutType(const std::vector<Offer>& offers,
                       std::vector<Offer>& cpaOffers,
                       std::vector<Offer>& cpsOffers) {
    for (const auto& offer : offers) {
        if (offer.payout_type == "CPA") {
            cpaOffers.push_back(offer);
        } else if (offer.payout_type == "CPS") {
            cpsOffers.push_back(offer);
        }
        // Skip unknown payout types
    }
}

// ========== Get extra offset for coin toss ==========
// Returns 10 if random > 0.8, else 0
int getExtraOffset(const std::string& /*offer_id*/, std::mt19937& rng) {
    std::uniform_real_distribution<double> dist(0.0, 1.0);
    double r = dist(rng);
    return (r > 0.8) ? 10 : 0;
}

// ========== Coin toss: select between CPA and CPS offer ==========
// CPS is selected with probability (10% + extraOffset)%, otherwise CPA
// Returns the chosen offer_id
std::string coinTossSelect(const std::string& cpaOfferId, const std::string& cpsOfferId,
                           std::mt19937& rng) {
    // If only one is available, return it
    if (cpaOfferId.empty() && cpsOfferId.empty()) return "";
    if (cpaOfferId.empty()) return cpsOfferId;
    if (cpsOfferId.empty()) return cpaOfferId;

    // Both available — do weighted coin toss
    int extraOffset = getExtraOffset(cpsOfferId, rng);
    double cpsProb = (10.0 + extraOffset) / 100.0;  // 10% base + 0 or 10 extra

    std::uniform_real_distribution<double> dist(0.0, 1.0);
    double r = dist(rng);

    if (r < cpsProb) {
        return cpsOfferId;
    } else {
        return cpaOfferId;
    }
}

// Match function: calls OpenAI API to find the best offer for a chat history
std::string matchOffer(const std::vector<Chat>& chatHistory, const std::vector<Offer>& offers,
                       const std::string& apiKey) {

    // Build the chat conversation text
    std::string conversation;
    for (const auto& chat : chatHistory) {
        conversation += chat.role + ": " + chat.text + "\n";
    }

    // Build the offers list text
    std::string offersList;
    for (const auto& offer : offers) {
        offersList += "ID: " + offer.offer_id + " | Name: " + offer.name +
                      " | Type: " + offer.payout_type + " | Amount: " + offer.payout_amount +
                      " | URL: " + offer.preview_url + "\n";
    }

    // Build the prompt
    std::string systemPrompt = "You are an ad-matching engine. Given a chat conversation and a list of affiliate offers, "
                               "pick the single most relevant offer for the user based on the conversation context. "
                               "Respond with ONLY the numeric Offer ID, nothing else. "
                               "If no offer is relevant, respond with an empty string.";

    std::string userPrompt = "Chat conversation:\n" + conversation +
                             "\nAvailable offers:\n" + offersList +
                             "\nWhich offer ID is most relevant to this conversation? Reply with ONLY the offer ID number.";

    // Build the JSON payload
    std::string payload = "{\"model\":\"gpt-4o-mini\","
                          "\"messages\":["
                          "{\"role\":\"system\",\"content\":\"" + jsonEscape(systemPrompt) + "\"},"
                          "{\"role\":\"user\",\"content\":\"" + jsonEscape(userPrompt) + "\"}"
                          "],\"max_tokens\":20,\"temperature\":0}";

    // Write payload to a temp file to avoid shell escaping issues
    std::string tmpFile = "/tmp/openai_payload.json";
    {
        std::ofstream ofs(tmpFile);
        ofs << payload;
        ofs.close();
    }

    // Build the curl command
    std::string cmd = "curl -s -X POST https://api.openai.com/v1/chat/completions "
                      "-H 'Content-Type: application/json' "
                      "-H 'Authorization: Bearer " + apiKey + "' "
                      "-d @" + tmpFile + " 2>&1";

    std::string response = execCommand(cmd);

    // Parse the offer_id from the response content
    std::string content = extractJsonString(response, "content");
    std::string offerId = trim(content);

    // Strip surrounding double-quotes if present (model sometimes wraps in quotes)
    while (offerId.size() >= 2 && offerId.front() == '"' && offerId.back() == '"') {
        offerId = offerId.substr(1, offerId.size() - 2);
    }
    offerId = trim(offerId);

    // If empty, no match — this is normal
    if (offerId.empty()) {
        return "";
    }

    // Validate it's a numeric offer ID
    bool isNumeric = true;
    for (char c : offerId) {
        if (!isdigit(c)) {
            isNumeric = false;
            break;
        }
    }

    if (!isNumeric) {
        std::cerr << "  Warning: Non-numeric offer ID received: '" << offerId << "'" << std::endl;
        return "";
    }

    return offerId;
}

int main() {
    const std::string API_KEY = "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";

    // ========== 1. Parse chat-data-3303.csv ==========
    std::string chat_filename = "data/chat-data-3303.csv";
    std::ifstream chat_file(chat_filename);

    if (!chat_file.is_open()) {
        std::cerr << "Error: Could not open file " << chat_filename << std::endl;
        return 1;
    }

    std::unordered_map<std::string, std::vector<Chat>> chats_by_visitor;

    std::string line;
    bool isFirstLine = true;
    int lineCount = 0;

    while (std::getline(chat_file, line)) {
        if (isFirstLine) {
            isFirstLine = false;
            continue;
        }

        std::vector<std::string> fields = parseCSVLine(line);

        if (fields.size() != 12) {
            lineCount++;
            continue;
        }

        Chat chat;
        chat.id = trim(fields[0]);
        chat.publisher_id = trim(fields[1]);
        chat.user_id = trim(fields[2]);
        chat.user_email = trim(fields[3]);
        chat.visitor_id = trim(fields[4]);
        chat.chat_id = trim(fields[5]);
        chat.session_id = trim(fields[6]);
        chat.url = trim(fields[7]);
        chat.request_headers = trim(fields[8]);
        chat.role = trim(fields[9]);
        chat.text = trim(fields[10]);
        chat.created_at = trim(fields[11]);

        chats_by_visitor[chat.visitor_id].push_back(chat);
        lineCount++;
    }

    chat_file.close();

    std::cout << "Parsed " << lineCount << " chat records." << std::endl;
    std::cout << "Found " << chats_by_visitor.size() << " unique visitors." << std::endl;

    // ========== 2. Parse offers.csv ==========
    std::string offers_filename = "data/offers.csv";
    std::ifstream offers_file(offers_filename);

    if (!offers_file.is_open()) {
        std::cerr << "Error: Could not open file " << offers_filename << std::endl;
        return 1;
    }

    std::vector<Offer> offers;
    isFirstLine = true;

    while (std::getline(offers_file, line)) {
        if (isFirstLine) {
            isFirstLine = false;
            continue;
        }

        std::vector<std::string> fields = parseCSVLine(line);

        if (fields.size() != 7) continue;

        Offer offer;
        offer.offer_id = trim(fields[0]);
        offer.name = trim(fields[1]);
        offer.preview_url = trim(fields[2]);
        offer.payout_type = trim(fields[3]);
        offer.payout_amount = trim(fields[4]);
        offer.payout_percentage = trim(fields[5]);
        offer.click_to_run = trim(fields[6]);

        // Populate derived fields
        extractCountries(offer);
        offer.payout_amount_val = parsePayout(offer.payout_amount);
        offer.payout_percentage_val = parsePercentage(offer.payout_percentage);

        offers.push_back(offer);
    }

    offers_file.close();

    std::cout << "Parsed " << offers.size() << " offers." << std::endl;

    // ========== 3. Parse ad-slots-3303.csv ==========
    std::string slots_filename = "data/ad-slots-3303.csv";
    std::ifstream slots_file(slots_filename);

    if (!slots_file.is_open()) {
        std::cerr << "Error: Could not open file " << slots_filename << std::endl;
        return 1;
    }

    std::vector<AdSlot> adSlots;
    isFirstLine = true;

    while (std::getline(slots_file, line)) {
        if (isFirstLine) {
            isFirstLine = false;
            continue;
        }

        std::vector<std::string> fields = parseCSVLine(line);

        if (fields.size() != 9) {
            std::cerr << "Warning: ad-slot line has " << fields.size()
                      << " fields, expected 9. Skipping." << std::endl;
            continue;
        }

        AdSlot slot;
        slot.id = trim(fields[0]);
        slot.visitor_id = trim(fields[1]);
        slot.session_id = trim(fields[2]);
        slot.chat_id = trim(fields[3]);
        slot.assistant_message_count = std::stoi(trim(fields[4]));
        slot.chat_history_length = std::stoi(trim(fields[5]));
        slot.user_message_count = std::stoi(trim(fields[6]));
        slot.geo_country_code = trim(fields[7]);
        slot.created_at = trim(fields[8]);

        adSlots.push_back(slot);
    }

    slots_file.close();

    std::cout << "Parsed " << adSlots.size() << " ad slots." << std::endl;

    // ========== 4. Process each ad slot: match to an offer ==========
    std::vector<std::pair<std::string, std::string>> results; // {slot_id, offer_id}

    // Initialize random number generator
    std::random_device rd;
    std::mt19937 rng(rd());

    std::cout << "\nProcessing ad slots..." << std::endl;

    // Print offer geo stats
    {
        int allCountries = 0, withCountries = 0, noCountries = 0;
        for (const auto& o : offers) {
            if (o.all_countries) allCountries++;
            else if (!o.countries.empty()) withCountries++;
            else noCountries++;
        }
        std::cout << "Offer geo breakdown: " << allCountries << " all-countries, "
                  << withCountries << " with specific countries, "
                  << noCountries << " no country detected" << std::endl;
    }

    for (size_t i = 0; i < adSlots.size(); ++i) {
        const AdSlot& slot = adSlots[i];

        std::cout << "[" << (i + 1) << "/" << adSlots.size() << "] "
                  << "Slot: " << slot.id
                  << " | Visitor: " << slot.visitor_id
                  << " | Geo: " << slot.geo_country_code
                  << " | History length: " << slot.chat_history_length << std::endl;

        // Find the chat history for this visitor
        auto it = chats_by_visitor.find(slot.visitor_id);
        if (it == chats_by_visitor.end()) {
            std::cerr << "  No chats found for visitor " << slot.visitor_id << std::endl;
            results.push_back({slot.id, ""});
            continue;
        }

        const std::vector<Chat>& allChats = it->second;

        // Extract the first N chats (dictated by chat_history_length)
        int n = std::min(slot.chat_history_length, (int)allChats.size());
        std::vector<Chat> chatSubset(allChats.begin(), allChats.begin() + n);

        // Step 1: Filter offers by geo country code
        std::vector<Offer> geoFiltered = filterOffersByGeo(offers, slot.geo_country_code);
        std::cout << "  Geo-filtered offers for " << slot.geo_country_code
                  << ": " << geoFiltered.size() << " offers" << std::endl;

        if (geoFiltered.empty()) {
            std::cout << "  No offers available for country " << slot.geo_country_code << std::endl;
            results.push_back({slot.id, ""});
            continue;
        }

        // Step 2: Group by payout type
        std::vector<Offer> cpaOffers, cpsOffers;
        groupByPayoutType(geoFiltered, cpaOffers, cpsOffers);
        std::cout << "  CPA offers: " << cpaOffers.size()
                  << " | CPS offers: " << cpsOffers.size() << std::endl;

        // Step 3: Call OpenAI separately for each non-empty group
        std::string cpaOfferId, cpsOfferId;

        if (!cpaOffers.empty()) {
            cpaOfferId = matchOffer(chatSubset, cpaOffers, API_KEY);
            std::cout << "  CPA match: " << (cpaOfferId.empty() ? "(none)" : cpaOfferId) << std::endl;
        }

        if (!cpsOffers.empty()) {
            cpsOfferId = matchOffer(chatSubset, cpsOffers, API_KEY);
            std::cout << "  CPS match: " << (cpsOfferId.empty() ? "(none)" : cpsOfferId) << std::endl;
        }

        // Step 4: Coin toss to select final offer
        std::string finalOfferId = coinTossSelect(cpaOfferId, cpsOfferId, rng);
        std::cout << "  Final offer: " << (finalOfferId.empty() ? "(none)" : finalOfferId) << std::endl;

        results.push_back({slot.id, finalOfferId});
    }

    // ========== 5. Export results to output.csv ==========
    std::string output_filename = "output.csv";
    std::ofstream output_file(output_filename);

    if (!output_file.is_open()) {
        std::cerr << "Error: Could not open output file " << output_filename << std::endl;
        return 1;
    }

    output_file << "ad_slot_id,offer_id" << std::endl;
    for (const auto& result : results) {
        output_file << result.first << "," << result.second << std::endl;
    }

    output_file.close();

    std::cout << "\nResults exported to " << output_filename << std::endl;
    std::cout << "Total slots processed: " << results.size() << std::endl;

    int matched = 0;
    for (const auto& r : results) {
        if (!r.second.empty()) matched++;
    }
    std::cout << "Slots matched with an offer: " << matched << std::endl;

    return 0;
}
