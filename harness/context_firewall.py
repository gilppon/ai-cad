import json

def truncate_data(data, max_len=1000):
    """
    Truncates large data (strings, lists, dicts) for safe logging and context management.
    """
    if isinstance(data, str):
        if len(data) > max_len:
            return data[:max_len] + f"... [TRUNCATED {len(data)-max_len} chars]"
        return data
    elif isinstance(data, list):
        if len(data) > 10:
            return [truncate_data(item, max_len=100) for item in data[:10]] + [f"... [TRUNCATED {len(data)-10} items]"]
        return [truncate_data(item, max_len=100) for item in data]
    elif isinstance(data, dict):
        if len(data) > 10:
            truncated = {k: truncate_data(v, max_len=100) for k, v in list(data.items())[:10]}
            truncated["_rest_"] = f"... [TRUNCATED {len(data)-10} keys]"
            return truncated
        return {k: truncate_data(v, max_len=100) for k, v in data.items()}
    return data

def firewall_log(label, data):
    """
    Safe log that prevents context pollution.
    """
    safe_data = truncate_data(data)
    print(f"[{label}] {json.dumps(safe_data, indent=2, ensure_ascii=False)}")
