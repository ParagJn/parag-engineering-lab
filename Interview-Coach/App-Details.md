## Interview Coaching App

I want a new app that needs to be build that is designed to help users prepare for job interviews. The app will provide personalized coaching, practice questions, and feedback to improve interview skills.

Key features of the app will include:

Ask user to to upload the company name, job descrition, title 
Then ask user for the profile, years of experience 

Give user an option for the following rounds of interview
Technical or Management or Salary negotiation or behavioral

Once the user select the interview type, then i want the app to have 3 agents to agree questions. 

Agent 1 will be chatgpt based. 
Agent 2 will be gemini based
and Agent 3 will be Anthropic claude. 

Just as a interview process, any of the agent can ask the relevant question and wait for the response from the user. 

Once the response is provided, it will be evaluated by all three agents, and they will provide score between 1 and 10 with 10 being best.  on the user's answer. 
user will have an option to receive a consolidated feedback that is based on the evaluations from all three agents.

### Additional Features
The app needs to be compatible with mobile web browser and should have a user-friendly interface. It should also include the following additional features:
- A dashboard to track progress and performance over time.
- each interview to have 6 top questions relevant to the selected interview type and job description and requirement from the company.. 
- analyze the company's profile and history when framing the questions. Example if the company is ChatGPt, the questions about AI iwll be very tough and if the company is a captive style company, the questions will be more about process and management that uses AI etc. so have this in mind when framing the questions.

## Session management

User local file sytem and json files to create a session management system to store the user's progress, answers, and feedback. This will allow users to resume their interview practice sessions at any time without losing their previous data.

## Foler strucrures
Create proper folder structure for the app to ensure maintainability and scalability. The backend and frontend components should be clearly separated, with dedicated folders for models, routes, services, and utilities in the backend, and components, pages, and assets in the frontend.

## start.sh 
create a start.sh script to automate the setup and deployment of the app. This script should handle tasks such as installing dependencies, setting environment variables, and starting the backend and frontend servers.
it needs to verify the libraries installed and if not installed, it should install the latest version of the libraries for both froentend and backend.

## venv
use this for python venv : /Users/paragjain/dev-works/myenv

## config file
build config file to store the api keys and other configuration settings. This will allow for easy management of sensitive information and make it easier to update the app's settings without modifying the codebase.
try to add as much as you can to config so that its easy to manage the app's settings and configurations. The config file should be structured in a way that allows for easy access and modification of the settings, and should include options for customizing the app's behavior and appearance.

Below is the api keys and the code on how to use it. 

SAP_CLIENT_ID=sb-327a9111-6cf6-4d91-ace7-37d99b518309!b186266|aicore!b540
SAP_CLIENT_SECRET=ea10318d-5644-4528-b903-d220f536c319$jG8xsYd9wWXV_KLdTJYwo7_D4e_sepIFJj8JZYwBBr0=
SAP_TOKEN_URL=https://ibm-lss.authentication.eu10.hana.ondemand.com/oauth/token
SAP_API_URL=https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d021935c4e8c3985/v2/completion
SAP_RESOURCE_GROUP=genius
SAP_MODEL_DISCOVERY_URL=https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/lm/scenarios/foundation-models/models
SAP_ANTHROPIC_MODEL=anthropic--claude-4.6-opus
SAP_GEMINI_MODEL=gemini-2.5-pro
SAP_THINKING_MODE=adaptive
SAP_THINKING_BUDGET_TOKENS=12000


How to use this API keys is the code below

# Import required libraries
import requests
import json
from datetime import datetime, timedelta

# Environment Variables - SAP AI Core Credentials -- 
SAP_CLIENT_ID = "sb-327a9111-6cf6-4d91-ace7-37d99b518309!b186266|aicore!b540"
SAP_CLIENT_SECRET = "ea10318d-5644-4528-b903-d220f536c319$jG8xsYd9wWXV_KLdTJYwo7_D4e_sepIFJj8JZYwBBr0="
SAP_TOKEN_URL = "https://ibm-lss.authentication.eu10.hana.ondemand.com/oauth/token"
SAP_API_URL = "https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d021935c4e8c3985/v2/completion"
SAP_RESOURCE_GROUP = "genius"

# Function to get OAuth Access Token
# This function is needed to generate access tokens for authenticating API requests.
def get_access_token():
    """
    Generate OAuth 2.0 access token using SAP AI Core service key credentials.
    """
    try:
        token_payload = {
            'grant_type': 'client_credentials',
            'client_id': SAP_CLIENT_ID,
            'client_secret': SAP_CLIENT_SECRET
        }
        
        response = requests.post(
            SAP_TOKEN_URL,
            data=token_payload,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get('access_token')
        
        print(f"✅ Access token generated successfully")
        print(f"Token expires in: {token_data.get('expires_in', 'N/A')} seconds")
        
        return access_token
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Error generating access token: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return None

The models to use are : 

gemini-2.5-pro
anthropic--claude-4.7-opus
gpt-5.5                        


The app needs to be fastapi based for backend, and react tailwin/css and latest node.js libraries for frontend. The app should be designed to be scalable and maintainable, with clear separation of concerns between the frontend and backend components.

Keep the color business friendly and neutral with white background. 

Plan this and ask questions if any ambiguity arises before starting the development process to ensure that all requirements are clear and achievable.

