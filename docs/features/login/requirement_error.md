{
    "index": {
        "feature": "login",
        "use_cases": [
            {
                "id": "UC-LOGIN-1",
                "title": "Standard ID/Password Login",
                "actor": "User",
                "trigger": "User submits login form with credentials",
                "preconditions": [
                    "User has a registered account"
                ],
                "happy_path": [
                    "Client identifies login type as IDPassword",
                    "Client calls addCountryCodeToPayload",
                    "Client sends POST request to /auth/login with mode MULTI_AUTH",
                    "Server validates credentials",
                    "Server returns UserSession"
                ],
                "edge_cases": [
                    "Invalid credentials",
                    "Account locked",
                    "Missing country code"
                ],
                "business_value": "Provides secure access to user-specific features and data.",
                "api_paths": [
                    "POST /auth/login"
                ],
                "evidence_refs": [
                    {
                        "file": "src/lib/apis/user.ts",
                        "symbol": "UserAPIs.login"
                    }
                ]
            },
            {
                "id": "UC-LOGIN-2",
                "title": "Social OAuth Login",
                "actor": "User",
                "trigger": "User selects Kakao, Google, or Naver login option",
                "preconditions": [
                    "User has a valid third-party account"
                ],
                "happy_path": [
                    "Client identifies loginTypeCD (KakaoOpenID, GoogleOpenID, or NaverOpenID)",
                    "Client selects specific endpoint (e.g., /auth/login-by-kakao)",
                    "Client sends POST request with OAuth payload and mode MULTI_AUTH",
                    "Server validates third-party token",
                    "Server returns UserSession"
                ],
                "edge_cases": [
                    "Third-party authentication failure",
                    "User cancels OAuth flow",
                    "Email mismatch between providers"
                ],
                "business_value": "Reduces onboarding friction and improves conversion rates.",
                "api_paths": [
                    "POST /auth/login-by-google",
                    "POST /auth/login-by-kakao",
                    "POST /auth/login-by-naver"
                ],
                "evidence_refs": [
                    {
                        "file": "src/lib/apis/user.ts",
                        "symbol": "UserAPIs.login"
                    }
                ]
            },
            {
                "id": "UC-LOGIN-3",
                "title": "Password Recovery and Reset",
                "actor": "User",
                "trigger": "User requests password reset via phone number",
                "preconditions": [
                    "User has a registered phone number"
                ],
                "happy_path": [
                    "User requests OTP via /auth/forgot-password",
                    "User receives and verifies OTP",
                    "User submits new password to /auth/reset-password",
                    "Server updates password record"
                ],
                "edge_cases": [
                    "Expired OTP",
                    "Invalid phone number format",
                    "Password complexity requirements not met"
                ],
                "business_value": "Allows users to regain access to accounts without manual support intervention.",
                "api_paths": [
                    "POST /auth/forgot-password",
                    "POST /auth/reset-password"
                ],
                "evidence_refs": [
                    {
                        "file": "src/lib/apis/user.ts",
                        "symbol": "UserAPIs.getOptByPhoneNumber"
                    },
                    {
                        "file": "src/lib/apis/user.ts",
                        "symbol": "UserAPIs.resetPassword"
                    }
                ]
            },
            {
                "id": "UC-LOGIN-4",
                "title": "Account Withdrawal",
                "actor": "User",
                "trigger": "User decides to delete their account",
                "preconditions": [
                    "User is authenticated"
                ],
                "happy_path": [
                    "User fetches withdrawal reasons via /withdraw-reasons",
                    "User selects a reason and submits /withdraw request",
                    "Server processes account deactivation/deletion"
                ],
                "edge_cases": [
                    "Pending orders preventing withdrawal",
                    "Invalid withdrawal reason code"
                ],
                "business_value": "Ensures compliance with data privacy regulations (GDPR/CCPA) and user autonomy.",
                "api_paths": [
                    "GET /withdraw-reasons",
                    "POST /withdraw"
                ],
                "evidence_refs": [
                    {
                        "file": "src/lib/apis/user.ts",
                        "symbol": "UserAPIs.getReasons"
                    },
                    {
                        "file": "src/lib/apis/user.ts",
                        "symbol": "UserAPIs.withdraw"
                    }
                ]
            }
        ],
        "endpoints": [
            {
                "method": "GET",
                "path": "/auth/b2c/org-code/validate",
                "handler_file": "UNKNOWN (Evidence Gap)",
                "handler_function": "UNKNOWN (Evidence Gap)",
                "auth_required": false,
                "service_chain": [
                    "UserAPIs.v
...[truncated]...