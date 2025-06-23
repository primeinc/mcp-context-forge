import { PublicClientApplication } from '@azure/msal-browser';
import './styles.css';

// MSAL Configuration
const msalConfig = {
    auth: {
        clientId: window.APP_CONFIG.AZURE_CLIENT_ID,
        authority: `${window.APP_CONFIG.AZURE_AUTHORITY_HOST}/${window.APP_CONFIG.AZURE_TENANT_ID}`,
        redirectUri: window.APP_CONFIG.WEB_REDIRECT_URI || window.location.origin + '/auth/callback'
    },
    cache: {
        cacheLocation: 'sessionStorage',
        storeAuthStateInCookie: false
    }
};

// API Configuration
const apiConfig = {
    scopes: [`${window.APP_CONFIG.API_BASE_URL}/.default`],
    baseUrl: window.APP_CONFIG.API_BASE_URL
};

// Initialize MSAL instance
const msalInstance = new PublicClientApplication(msalConfig);

// Initialize MSAL
msalInstance.initialize().then(() => {
    console.log('MSAL initialized');
});

// Alpine.js app data
function mcpApp() {
    return {
        isAuthenticated: false,
        isLoading: true,
        userDisplayName: '',
        activeTab: 'servers',
        accessToken: null,

        async init() {
            try {
                // Handle redirect response
                const response = await msalInstance.handleRedirectPromise();
                if (response) {
                    this.handleAuthResponse(response);
                }

                // Check if user is already logged in
                const accounts = msalInstance.getAllAccounts();
                if (accounts.length > 0) {
                    msalInstance.setActiveAccount(accounts[0]);
                    this.isAuthenticated = true;
                    this.userDisplayName = accounts[0].name || accounts[0].username;
                    await this.acquireAccessToken();
                    this.setupHtmxAuth();
                }
            } catch (error) {
                console.error('Auth initialization error:', error);
            } finally {
                this.isLoading = false;
            }
        },

        async signIn() {
            this.isLoading = true;
            try {
                const loginRequest = {
                    scopes: apiConfig.scopes,
                    prompt: 'select_account'
                };

                await msalInstance.loginRedirect(loginRequest);
            } catch (error) {
                console.error('Sign in error:', error);
                this.isLoading = false;
            }
        },

        async signOut() {
            this.isLoading = true;
            try {
                const logoutRequest = {
                    account: msalInstance.getActiveAccount(),
                    postLogoutRedirectUri: window.location.origin
                };

                await msalInstance.logoutRedirect(logoutRequest);
            } catch (error) {
                console.error('Sign out error:', error);
                this.isLoading = false;
            }
        },

        handleAuthResponse(response) {
            if (response.account) {
                msalInstance.setActiveAccount(response.account);
                this.isAuthenticated = true;
                this.userDisplayName = response.account.name || response.account.username;
                this.acquireAccessToken();
                this.setupHtmxAuth();
            }
        },

        async acquireAccessToken() {
            try {
                const tokenRequest = {
                    scopes: apiConfig.scopes,
                    account: msalInstance.getActiveAccount()
                };

                const response = await msalInstance.acquireTokenSilent(tokenRequest);
                this.accessToken = response.accessToken;
                return response.accessToken;
            } catch (error) {
                console.error('Token acquisition error:', error);
                if (error.name === 'InteractionRequiredAuthError') {
                    // Fallback to interactive method
                    await msalInstance.acquireTokenRedirect(tokenRequest);
                }
            }
        },

        setupHtmxAuth() {
            // Configure HTMX to include Bearer token in all requests
            document.body.addEventListener('htmx:configRequest', (event) => {
                if (this.accessToken) {
                    event.detail.headers['Authorization'] = `Bearer ${this.accessToken}`;
                }
            });

            // Handle 401 responses by refreshing token
            document.body.addEventListener('htmx:responseError', async (event) => {
                if (event.detail.xhr.status === 401) {
                    await this.acquireAccessToken();
                    // Retry the request
                    event.detail.target.dispatchEvent(new Event('htmx:trigger'));
                }
            });
        }
    };
}

// Make mcpApp available globally for Alpine.js
window.mcpApp = mcpApp;