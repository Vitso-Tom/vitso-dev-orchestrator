const isSecure = window.location.protocol === 'https:';
const API_HOST = window.location.hostname;
const API_PORT = window.location.port || (isSecure ? 443 : 80);

export const API_BASE_URL = `${window.location.protocol}//${API_HOST}:${API_PORT}`;
export const WS_BASE_URL = `${isSecure ? 'wss' : 'ws'}://${API_HOST}:${API_PORT}`;
