targetScope = 'resourceGroup'

@description('Lab region; model support and quota were checked here.')
param location string = 'eastus2'

@description('Operator object ID in the deployment tenant, not the home tenant.')
param operatorObjectId string

@description('Optional stable client IP. Leave empty when corporate egress rotates; Entra identity and subscription remain required.')
param callerIp string = ''

@description('Lab owner contact.')
param publisherEmail string = 'lab-owner@example.com'

@description('Names for the isolated reproduction resources.')
param foundryName string = 'ai-token-lab-example'

@description('Globally unique classic gateway name; keep it aligned with LAB_APIM_CLASSIC_NAME.')
param classicGatewayName string = 'apim-lab-classic-example'

@description('Globally unique v2 gateway name; keep it aligned with LAB_APIM_V2_NAME.')
param v2GatewayName string = 'apim-lab-v2-example'

@description('Foundry project name.')
param projectName string = 'project-token-lab'

@description('The shared model deployment for both API schemas.')
param deploymentName string = 'lab-model'

var tags = {
  purpose: 'synthetic-apim-token-repro'
  case: 'SUPPORT-CASE-REDACTED'
  environment: 'lab'
  owner: 'lab-owner'
}

var gatewayDefinitions = [
  {
    name: classicGatewayName
    sku: 'Developer'
  }
  {
    name: v2GatewayName
    sku: 'BasicV2'
  }
]

module foundry 'modules/foundry.bicep' = {
  name: 'foundry'
  params: {
    location: location
    name: foundryName
    projectName: projectName
    deploymentName: deploymentName
    operatorObjectId: operatorObjectId
    tags: tags
  }
}

module gateways 'modules/gateway.bicep' = [for gateway in gatewayDefinitions: {
  name: gateway.name
  params: {
    location: location
    name: gateway.name
    sku: gateway.sku
    publisherEmail: publisherEmail
    callerIp: callerIp
    operatorObjectId: operatorObjectId
    tags: tags
  }
}]

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: account
  name: projectName
}

resource gatewayModelRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (gateway, index) in gatewayDefinitions: {
  name: guid(account.id, gateway.name, 'openai-user')
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: gateways[index].outputs.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [foundry]
}]

resource gatewayProjectRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (gateway, index) in gatewayDefinitions: {
  name: guid(project.id, gateway.name, 'foundry-user')
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    principalId: gateways[index].outputs.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [foundry]
}]

output projectEndpoint string = foundry.outputs.projectEndpoint
output openaiEndpoint string = foundry.outputs.openaiEndpoint
output gateways array = [for (gateway, index) in gatewayDefinitions: {
  name: gateway.name
  sku: gateway.sku
  url: gateways[index].outputs.gatewayUrl
}]
