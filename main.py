# importing boto3 for communication with dynamoDB
import boto3
from boto3.dynamodb.conditions import Key, Attr
from fastapi import Security, Depends, FastAPI, HTTPException
from fastapi.security.api_key import APIKeyQuery, APIKeyCookie, APIKeyHeader, APIKey
from fastapi_cloudauth.cognito import Cognito, CognitoCurrentUser, CognitoClaims
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from starlette.status import HTTP_403_FORBIDDEN
from starlette.responses import RedirectResponse, JSONResponse
from faker import Faker
from cryptography.fernet import Fernet
# key = Fernet.generate_key()
key= '-OiJlttOaFGgb_8GVAsJRy5c8sokNizC1BZ8GGt2TX8='
faker = Faker()
cipher_suite = Fernet(key)


# parameters for authentication
API_KEY = "123abc"
API_KEY_NAME = "access_token"
COOKIE_DOMAIN = "localtest.me"
"""api_key_query = APIKeyQuery(name=API_KEY_NAME, auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
api_key_cookie = APIKeyCookie(name=API_KEY_NAME, auto_error=False)
async def get_api_key(
    api_key_query: str = Security(api_key_query),
    api_key_header: str = Security(api_key_header),
    api_key_cookie: str = Security(api_key_cookie),
):
    if api_key_query == API_KEY:
        return api_key_query
    elif api_key_header == API_KEY:
        return api_key_header
    elif api_key_cookie == API_KEY:
        return api_key_cookie
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials"
        ) """

userRegion = "us-east-1"
userClientId = "4hkma6pavubar061g3u11fek9q"
usrPoolId= "us-east-1_o7TlGk5JE"
cidp = boto3.client('cognito-idp')
auth = Cognito(region= userRegion, userPoolId= usrPoolId)
getUser = CognitoCurrentUser(region= userRegion, userPoolId= usrPoolId)


#app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
# Route to the homepage - does not require authentication
app = FastAPI()
@app.get("/", tags=["Homo"])
async def homepage():
    return "Welcome to API homepage!"


# Sign Up
@app.get("/createUser", tags=["Create User"])
async def sign_up_cognito(usrName: str, usrPassword: str):
    cidp.sign_up(ClientId= userClientId, Username= usrName, Password= usrPassword)
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('User_details') # made already
    response = table.put_item(
       Item={
            'Username': usrName, #partition key
            'Password': usrPassword,
        }
    )
    result = "User Created. Confirm Sign Up"
    return response,result

# Confirm Sign up
@app.get("/confirmUser", tags=["Confirm User"])
async def create_user_on_cognito(usrName: str, usrPassword: str):
    cidp.admin_confirm_sign_up(UserPoolId= usrPoolId, Username= usrName)
   
    return "User Confirmed"

# Generate JWT Token
@app.get("/tokens", tags=["Generate TOkens"])
async def generate_JWT_token(usrName: str, usrPassword: str):
    JWT = cidp.admin_initiate_auth(UserPoolId= usrPoolId, ClientId= userClientId, AuthFlow= "ADMIN_NO_SRP_AUTH", AuthParameters= { "USERNAME": usrName, "PASSWORD": usrPassword })   
    AccessToken = JWT["AuthenticationResult"]["AccessToken"]
    RefreshToken = JWT["AuthenticationResult"]["RefreshToken"]
    IDToken = JWT["AuthenticationResult"]["IdToken"]
    refreshToken = cidp.admin_initiate_auth(UserPoolId= usrPoolId, ClientId= userClientId, AuthFlow= "REFRESH_TOKEN_AUTH", AuthParameters= {"REFRESH_TOKEN" : RefreshToken})
    dynamodb = boto3.resource('dynamodb')
    refreshToken = refreshToken["AuthenticationResult"]["IdToken"]
    table = dynamodb.Table('Tokens') 
    response = table.update_item(Key = {'Username': usrName},
        UpdateExpression="set RefreshToken=:r,JWT=:t,AccessToken=:a,IDToken=:i",
        ExpressionAttributeValues={
            ':t':JWT,
            ':a': AccessToken,
            ':r': refreshToken,
            ':i': IDToken
        }
    )
    result = "Tokens Created"
    return response,result,refreshToken

@app.get("/anonymizeuserName", tags=["Encrypt"])
async def anonymizeFields(currentUser: CognitoClaims = Depends(getUser)):
    fakename = faker.name()
    username = currentUser.username
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Username_fake') 
    response = table.update_item(Key = {'username': username},
        UpdateExpression="set fakename=:f",
        ExpressionAttributeValues={
            ':f': fakename
        }
    )
    return response, fakename

@app.get("/fakestockdata", tags=["Fake_Data"])
async def fakedata(stockdate: str,currentUser: CognitoClaims = Depends(getUser)):
    stocks = query_date(stockdate)
    for x in stocks:
        x['name']=cipher_suite.encrypt(x['name'].encode())
    return stocks

# Logout page to delete cookies and block user from accessing the data
@app.get("/logout")
async def route_logout_and_remove_cookie():
    response = RedirectResponse(url="/")
    response.delete_cookie(API_KEY_NAME, domain=COOKIE_DOMAIN)
    return response
# Access the Swagger//Documentation page
# To access - with token - http://localtest.me:8000/documentation?access_token=123abc
"""@app.get("/documentation", tags=["documentation"])
async def get_documentation(api_key: APIKey = Depends(get_api_key)):
    response = get_swagger_ui_html(openapi_url="/openapi.json", title="docs")
    response.set_cookie(
        API_KEY_NAME,
        value=api_key,
        domain=COOKIE_DOMAIN,
        httponly=True,
        max_age=1800,
        expires=1800,
    )
    return response"""
    
#@app.get("/openapi.json", tags=["documentation"])
"""async def get_open_api_endpoint(api_key: APIKey = Depends(get_api_key)):
    response = JSONResponse(
        get_openapi(title="FastAPI security test", version=1, routes=app.routes)
    )
    return response"""
def query_from_stock_name(name, dynamodb=None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Data_Store')
    response = table.query(
        KeyConditionExpression=Key('name').eq(name)
    )
    return response['Items']

# Route for getting data by stock name
@app.get("/databyname")
async def dataPage(stockName: str,currentUser: CognitoClaims = Depends(getUser)):
    stocks = query_from_stock_name(stockName)
    return stocks

def query_from_type(stocktype, dynamodb=None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Data_Store')
    response = table.scan(
        FilterExpression=Attr('type').eq(stocktype)
    )
    return response['Items']

# Route for getting data by stock type
@app.get("/databytype")
async def dataPage_1(stocktype: str,currentUser: CognitoClaims = Depends(getUser)):
    stocks = query_from_type(stocktype)
    return stocks

def query_date(stockdate, dynamodb=None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Data_Store')
    response = table.scan(
        FilterExpression=Attr('date').eq(stockdate)
    )
    return response['Items']

# Route for getting data by stock date
@app.get("/databydate")
async def dataPage_2(stockdate: str,currentUser: CognitoClaims = Depends(getUser)):
    stocks = query_date(stockdate)
    return stocks