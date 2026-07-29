Analyze the frontend completely, this is a fully functional frontend application built using React. The frontend is structured into several components, each responsible for a specific part of the user interface. The main components include:

However, there is not intelligence built into this. So now its time to add some intelligence to the frontend. 

I have created a new folder called backend and copied the env file over there. We need to use the fastapi based backend to add intelligence to the frontend. The backend will handle API requests and provide data to the frontend components.`

Python venv path is : /Users/paragjain/dev-works/myenv -- this is where the virtual environment for the backend is located. Make sure to activate this environment before running any backend scripts or installing dependencies.

The sample code to use the backend env file is below. 

-- sampple code -- 

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


-- End of sample coee. 

The model to use is : 
anthropic--claude-4.8-opus

First Step - 

Build a reusable class file that will allow me to use the LLM model using the SAP AI Core API. This class should handle the authentication, token management, and API requests to the model. It should also provide methods to send prompts to the model and receive responses. Make this re-usable so that i can later make this as common module for all my projeccts. 

Generate a config.json file that will allow me to pick and choose model choices. Example config.json structure:

Using SAP API = Y
Model Name : anthropic--claude-4.8-opus
Use = Y
Model Name : openai--gpt-4.1
Use = N

And so on. This way, I can easily switch between different models and control which ones are active for your application.

Add more intelligence to this json file, in case i would like to use OpenAI or Gemini Model in future, i can directly add them to the config.json file without changing the code. The config.json should be structured in a way that allows for easy addition of new models and their configurations. so it needs model name, endpint, and any other necessary parameters for each model.

Lets start with this and then add more features along the way. 