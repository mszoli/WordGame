async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
        opts.headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    let data = null;
    try {
        data = await res.json();
    } catch (e) {
        data = null;
    }
    if (!res.ok) {
        const message = (data && data.detail) ? data.detail : `Hiba (${res.status})`;
        throw new Error(message);
    }
    return data;
}

function tokenKey(gameId) {
    return `wordgame_token_${gameId}`;
}

function getStoredToken(gameId) {
    return localStorage.getItem(tokenKey(gameId));
}

function storeToken(gameId, token) {
    localStorage.setItem(tokenKey(gameId), token);
}
