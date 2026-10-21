@description('Region for the lab gateway.')
param location string

@description('Globally unique API Management service name.')
param name string

@description('Gateway generation to compare.')
@allowed(['Developer', 'BasicV2'])
param sku string

@description('Contact email for the lab owner.')
param publisherEmail string

@description('Optional stable caller IP. Empty uses the required Entra identity and APIM subscription controls.')
param callerIp string

@description('The operator object ID in the deployment tenant.')
param operatorObjectId string

@description('Cost attribution tags.')
param tags object

resource gateway 'Microsoft.ApiManagement/service@2024-05-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: sku
    capacity: 1
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: 'Synthetic token policy reproduction lab'
    publicNetworkAccess: 'Enabled'
    customProperties: sku == 'Developer' ? {
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls10': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls11': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Ssl30': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls10': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls11': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Ssl30': 'false'
    } : {}
  }
}

resource securityPolicy 'Microsoft.ApiManagement/service/policies@2024-05-01' = {
  parent: gateway
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: format('''
<policies>
  <inbound>
    {0}
    <validate-azure-ad-token tenant-id="{1}" output-token-variable-name="lab-caller">
      <audiences><audience>https://cognitiveservices.azure.com</audience></audiences>
      <required-claims><claim name="oid" match="all"><value>{2}</value></claim></required-claims>
    </validate-azure-ad-token>
  </inbound>
  <backend><forward-request /></backend>
  <outbound />
  <on-error />
</policies>
''', empty(callerIp) ? '' : format('<ip-filter action="allow"><address>{0}</address></ip-filter>', callerIp), subscription().tenantId, operatorObjectId)
  }
}

resource labSubscription 'Microsoft.ApiManagement/service/subscriptions@2024-05-01' = {
  parent: gateway
  name: 'repro'
  properties: {
    displayName: 'Isolated reproduction caller'
    scope: '/apis'
    state: 'active'
  }
}

output name string = gateway.name
output principalId string = gateway.identity.principalId
output gatewayUrl string = gateway.properties.gatewayUrl
