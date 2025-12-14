/**
 * AWS Amplify Configuration
 * 
 * This file configures AWS Amplify for Cognito authentication and API Gateway access.
 * Configuration values are loaded from environment variables:
 * - VITE_COGNITO_USER_POOL_ID: Cognito User Pool ID
 * - VITE_COGNITO_USER_POOL_CLIENT_ID: Cognito User Pool Client ID
 * - VITE_API_GATEWAY_URL: API Gateway base URL
 * - VITE_AWS_REGION: AWS region (defaults to us-east-1)
 */

import { Amplify } from 'aws-amplify';

// Get configuration from environment variables
const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID;
const userPoolWebClientId = import.meta.env.VITE_COGNITO_USER_POOL_CLIENT_ID;
const apiGatewayUrl = import.meta.env.VITE_API_GATEWAY_URL;
const awsRegion = import.meta.env.VITE_AWS_REGION || 'us-east-1';

// Validate required environment variables
if (!userPoolId) {
  console.warn('VITE_COGNITO_USER_POOL_ID is not set. Authentication will not work.');
}

if (!userPoolWebClientId) {
  console.warn('VITE_COGNITO_USER_POOL_CLIENT_ID is not set. Authentication will not work.');
}

if (!apiGatewayUrl) {
  console.warn('VITE_API_GATEWAY_URL is not set. API calls will fail.');
}

// Configure Amplify
Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: userPoolId || '',
      userPoolClientId: userPoolWebClientId || '',
      region: awsRegion,
      loginWith: {
        email: true,
        username: false,
        phone: false,
      },
      signUpVerificationMethod: 'code', // Email verification code
      userAttributes: {
        email: {
          required: true,
        },
      },
      allowGuestAccess: false,
    },
  },
  API: {
    REST: {
      docprof: {
        endpoint: apiGatewayUrl || '',
        region: awsRegion,
      },
    },
  },
});

export default Amplify;

