(function() {
    'use strict';

    const ACCESS_TOKEN_KEY = 'access_token';
    const USER_INFO_KEY = 'user_info';
    let restorePromise = null;

    function getAccessToken() {
        return localStorage.getItem(ACCESS_TOKEN_KEY);
    }

    function setAccessToken(token) {
        if (token) {
            localStorage.setItem(ACCESS_TOKEN_KEY, token);
        } else {
            localStorage.removeItem(ACCESS_TOKEN_KEY);
        }
    }

    function storeLogin(result) {
        setAccessToken(result && result.access_token);
        if (result && result.user) {
            localStorage.setItem(USER_INFO_KEY, JSON.stringify(result.user));
        }
    }

    function clearLocalSession() {
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(USER_INFO_KEY);
    }

    async function restoreAccessToken(force = false) {
        if (!force) {
            const currentToken = getAccessToken();
            if (currentToken) return currentToken;
        }

        if (restorePromise) return restorePromise;

        restorePromise = (async function() {
            try {
                const response = await window.fetch('/api/auth/restore-session', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Accept': 'application/json'
                    }
                });

                if (!response.ok) {
                    clearLocalSession();
                    return null;
                }

                const data = await response.json();
                if (!data.success || !data.access_token) {
                    clearLocalSession();
                    return null;
                }

                setAccessToken(data.access_token);
                return data.access_token;
            } catch (error) {
                console.error('Unable to restore login session:', error);
                return null;
            } finally {
                restorePromise = null;
            }
        })();

        return restorePromise;
    }

    function withAuthorization(options, token) {
        const requestOptions = Object.assign({}, options || {});
        const headers = new Headers(requestOptions.headers || {});
        if (token) headers.set('Authorization', `Bearer ${token}`);
        requestOptions.headers = headers;
        requestOptions.credentials = requestOptions.credentials || 'same-origin';
        return requestOptions;
    }

    async function authenticatedFetch(input, options) {
        let token = getAccessToken();
        if (!token) token = await restoreAccessToken();

        let response = await window.fetch(input, withAuthorization(options, token));
        if (response.status !== 401 && response.status !== 422) return response;

        // The access token may have expired. The HTTP-only Flask session lasts
        // longer and can safely issue a replacement token, then retry once.
        setAccessToken(null);
        token = await restoreAccessToken(true);
        if (!token) return response;

        response = await window.fetch(input, withAuthorization(options, token));
        return response;
    }

    function safeRedirectPath(value) {
        const path=String(value || '/');
        if(!path.startsWith('/')||path.startsWith('//')||/[\\\x00-\x1f]/.test(path))return '/';
        const target=new URL(path,window.location.origin);
        return target.origin===window.location.origin?target.pathname+target.search+target.hash:'/';
    }
    function loginUrl(redirectPath) {
        const redirect = redirectPath || `${window.location.pathname}${window.location.search}${window.location.hash}`;
        return `/auth/login?redirect=${encodeURIComponent(safeRedirectPath(redirect))}`;
    }

    function redirectToLogin(message, redirectPath) {
        clearLocalSession();
        if (message) sessionStorage.setItem('auth_notice', message);
        window.location.href = loginUrl(redirectPath);
    }

    window.CustomerAuth = {
        fetch: authenticatedFetch,
        getAccessToken,
        restoreAccessToken,
        storeLogin,
        clearLocalSession,
        redirectToLogin,
        safeRedirectPath
    };
})();
