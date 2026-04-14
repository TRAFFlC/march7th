#!/bin/bash

API_HOST="${API_HOST:-localhost}"
API_PORT="${API_PORT:-8000}"
TIMEOUT="${TIMEOUT:-10}"

check_api_health() {
    local url="http://${API_HOST}:${API_PORT}/"
    local response_code
    
    response_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "${TIMEOUT}" "${url}" 2>/dev/null)
    
    if [ "${response_code}" -eq 200 ]; then
        echo "API is healthy (HTTP ${response_code})"
        return 0
    else
        echo "API is unhealthy (HTTP ${response_code})"
        return 1
    fi
}

check_api_response() {
    local url="http://${API_HOST}:${API_PORT}/"
    local response
    
    response=$(curl -s --connect-timeout "${TIMEOUT}" "${url}" 2>/dev/null)
    
    if echo "${response}" | grep -q '"message"'; then
        echo "API response valid: ${response}"
        return 0
    else
        echo "API response invalid or empty"
        return 1
    fi
}

main() {
    echo "Checking API health at ${API_HOST}:${API_PORT}..."
    
    if check_api_health; then
        if check_api_response; then
            echo "Health check passed"
            exit 0
        else
            echo "Health check failed: Invalid response"
            exit 1
        fi
    else
        echo "Health check failed: API not responding"
        exit 1
    fi
}

main "$@"
