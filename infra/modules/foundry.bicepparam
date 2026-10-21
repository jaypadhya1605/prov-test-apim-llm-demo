using './foundry.bicep'

// Standalone example; use your approved names and target-tenant principal.
param location = 'eastus2'
param name = 'ai-token-lab-example'
param projectName = 'project-token-lab'
param deploymentName = 'lab-model'
param operatorObjectId = '00000000-0000-0000-0000-000000000003'
param tags = {
  purpose: 'synthetic-apim-token-repro'
  case: 'SUPPORT-CASE-REDACTED'
  environment: 'lab'
  owner: 'lab-owner'
}
