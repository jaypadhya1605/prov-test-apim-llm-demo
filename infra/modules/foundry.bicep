@description('Region with validated model quota.')
param location string

@description('Foundry account name and custom subdomain.')
param name string

@description('Project used to reproduce the project-scoped route.')
param projectName string

@description('Model deployment name.')
param deploymentName string

@description('Operator object ID in the deployment tenant.')
param operatorObjectId string

@description('Cost attribution tags.')
param tags object

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: name
  location: location
  tags: tags
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: name
    allowProjectManagement: true
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Synthetic token accounting reproduction'
    description: 'Synthetic-data experiment for support case SUPPORT-CASE-REDACTED.'
  }
}

resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: deploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: 100
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5-mini'
      version: '2025-08-07'
    }
    versionUpgradeOption: 'NoAutoUpgrade'
    raiPolicyName: 'Microsoft.Default'
  }
  dependsOn: [project]
}

resource operatorModelRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, operatorObjectId, 'openai-user')
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: operatorObjectId
    principalType: 'User'
  }
}

resource operatorProjectRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, operatorObjectId, 'foundry-user')
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    principalId: operatorObjectId
    principalType: 'User'
  }
}

output accountId string = account.id
output projectId string = project.id
output projectEndpoint string = 'https://${name}.services.ai.azure.com/api/projects/${projectName}'
output openaiEndpoint string = 'https://${name}.openai.azure.com/openai/v1'
