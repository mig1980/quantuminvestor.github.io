# Azure Managed Identity Migration Guide

This guide walks you through migrating from connection string authentication to Azure Managed Identity for Azure Blob Storage access.

## Overview

**Before**: Used `STORAGE_CONNECTION_STRING` secret with full account keys
**After**: Uses Azure Managed Identity (Workload Identity Federation) with federated credentials

### Benefits
- ✅ No secrets to rotate or manage
- ✅ Follows Azure security best practices
- ✅ Fine-grained access control with RBAC
- ✅ Automatic token renewal
- ✅ Better audit trails

---

## Prerequisites

- Azure subscription with owner/contributor access
- Azure Storage Account already created
- GitHub repository admin access
- Azure CLI installed (for local development)

---

## Step 1: Create Azure Service Principal (App Registration)

### Option A: Using Azure Portal

1. Navigate to **Azure Active Directory** → **App registrations**
2. Click **New registration**
   - Name: `github-actions-blog-newsletter`
   - Supported account types: `Single tenant`
   - Click **Register**
3. Note the following values (you'll need these later):
   - **Application (client) ID** → `AZURE_CLIENT_ID`
   - **Directory (tenant) ID** → `AZURE_TENANT_ID`

### Option B: Using Azure CLI

```bash
# Login to Azure
az login

# Create service principal
az ad sp create-for-rbac --name "github-actions-blog-newsletter" --role contributor \
    --scopes /subscriptions/{subscription-id}/resourceGroups/{resource-group-name} \
    --sdk-auth

# Note the output values:
# - clientId → AZURE_CLIENT_ID
# - tenantId → AZURE_TENANT_ID
# - subscriptionId → AZURE_SUBSCRIPTION_ID
```

---

## Step 2: Configure Workload Identity Federation

This allows GitHub Actions to authenticate to Azure without storing credentials.

### Using Azure Portal

1. Go to your **App Registration** → **Certificates & secrets**
2. Select **Federated credentials** tab
3. Click **Add credential**
4. Configure the federated credential:
   - **Federated credential scenario**: `GitHub Actions deploying Azure resources`
   - **Organization**: `mig1980` (your GitHub username/org)
   - **Repository**: `quantuminvestor` (your repo name)
   - **Entity type**: `Branch`
   - **Branch name**: `main`
   - **Credential name**: `github-actions-main-branch`
   - Click **Add**

### Using Azure CLI

```bash
# Get the App Registration Object ID
APP_OBJECT_ID=$(az ad app list --display-name "github-actions-blog-newsletter" --query "[0].id" -o tsv)

# Create federated credential
az ad app federated-credential create \
  --id $APP_OBJECT_ID \
  --parameters '{
    "name": "github-actions-main-branch",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:mig1980/quantuminvestor:ref:refs/heads/main",
    "description": "GitHub Actions federated credential for main branch",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

---

## Step 3: Assign Storage Blob Data Contributor Role

Grant the service principal permission to read/write blobs in your storage account.

### Using Azure Portal

1. Navigate to your **Storage Account**
2. Click **Access Control (IAM)** in the left menu
3. Click **Add** → **Add role assignment**
4. Select **Storage Blob Data Contributor** role
5. Click **Next**
6. Select **User, group, or service principal**
7. Click **Select members** and search for `github-actions-blog-newsletter`
8. Select it and click **Review + assign**

### Using Azure CLI

```bash
# Get your storage account resource ID
STORAGE_ACCOUNT_ID=$(az storage account show \
    --name {your-storage-account-name} \
    --resource-group {your-resource-group} \
    --query id -o tsv)

# Get the service principal Object ID (not App ID!)
SP_OBJECT_ID=$(az ad sp list --display-name "github-actions-blog-newsletter" --query "[0].id" -o tsv)

# Assign role
az role assignment create \
    --assignee-object-id $SP_OBJECT_ID \
    --role "Storage Blob Data Contributor" \
    --scope $STORAGE_ACCOUNT_ID \
    --assignee-principal-type ServicePrincipal
```

---

## Step 4: Configure GitHub Secrets

Add the following secrets to your GitHub repository:

### Navigate to GitHub Repository Settings

1. Go to your repository: `https://github.com/mig1980/quantuminvestor`
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** for each:

| Secret Name | Value | Where to Find |
|------------|-------|---------------|
| `AZURE_CLIENT_ID` | Application (client) ID | Azure Portal → App Registration → Overview |
| `AZURE_TENANT_ID` | Directory (tenant) ID | Azure Portal → App Registration → Overview |
| `AZURE_SUBSCRIPTION_ID` | Your Azure subscription ID | Azure Portal → Subscriptions |
| `STORAGE_ACCOUNT_NAME` | Storage account name (e.g., `stblogsubscriptions`) | Azure Portal → Storage Account → Overview |

### Important Notes
- **Remove** the old `STORAGE_CONNECTION_STRING` secret after migration
- Keep the secret names exact (case-sensitive)
- The workflow will fail until all 4 secrets are configured

---

## Step 5: Test the Migration

### Local Testing (Optional)

Before deploying, test locally using Azure CLI authentication:

```powershell
# Login to Azure
az login

# Set environment variable
$env:STORAGE_ACCOUNT_NAME = "your-storage-account-name"

# Test the script
cd scripts
python upload_newsletter_to_blob.py --latest
```

The script will use your Azure CLI credentials automatically via `DefaultAzureCredential`.

### GitHub Actions Testing

1. Commit and push the changes
2. Navigate to **Actions** tab in GitHub
3. Select **Generate & Upload Newsletter** workflow
4. Click **Run workflow**
5. Monitor the execution logs

Expected output:
```
✅ Newsletter uploaded successfully
📅 Week: X
📦 Blob: newsletters/weekX.html
```

---

## Troubleshooting

### Error: "STORAGE_ACCOUNT_NAME environment variable not set"

**Solution**: Verify the `STORAGE_ACCOUNT_NAME` secret is configured in GitHub repository settings.

### Error: "DefaultAzureCredential failed to retrieve a token"

**Causes**:
1. Federated credential not configured correctly
2. GitHub secrets missing or incorrect
3. Permissions not propagated yet (wait 5-10 minutes)

**Solution**: 
- Verify all 4 secrets are set in GitHub
- Check the federated credential matches your repo exactly: `repo:mig1980/quantuminvestor:ref:refs/heads/main`
- Ensure the service principal has the role assignment

### Error: "AuthorizationPermissionMismatch"

**Solution**: 
- Verify the service principal has **Storage Blob Data Contributor** role
- Wait 5-10 minutes for role assignment to propagate
- Check the role is assigned at the storage account level (not subscription)

### Error: "ModuleNotFoundError: No module named 'azure.identity'"

**Solution**: Install the updated dependencies:
```bash
pip install -r scripts/requirements.txt
```

---

## Rollback Plan

If you need to revert to connection string authentication:

1. Re-add the `STORAGE_CONNECTION_STRING` secret to GitHub
2. Revert the changes in these files:
   - `scripts/upload_newsletter_to_blob.py`
   - `.github/workflows/generate-newsletter-full.yml`
   - `scripts/requirements.txt`

---

## Security Best Practices

✅ **Do**:
- Use least privilege principle (Storage Blob Data Contributor, not Owner)
- Rotate federated credentials annually
- Monitor service principal activity via Azure AD logs
- Use separate service principals for different environments (dev/prod)

❌ **Don't**:
- Share client IDs publicly (they're not as sensitive as keys, but still shouldn't be public)
- Grant excessive permissions (e.g., Contributor or Owner roles)
- Use connection strings in production

---

## Additional Resources

- [Azure Workload Identity Federation](https://docs.microsoft.com/azure/active-directory/develop/workload-identity-federation)
- [GitHub Actions OIDC with Azure](https://docs.github.com/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-azure)
- [Azure Storage RBAC Roles](https://docs.microsoft.com/azure/storage/blobs/authorize-access-azure-active-directory)
- [DefaultAzureCredential](https://docs.microsoft.com/python/api/azure-identity/azure.identity.defaultazurecredential)

---

## Migration Checklist

- [ ] Create Azure service principal (App Registration)
- [ ] Configure federated credentials for GitHub Actions
- [ ] Assign Storage Blob Data Contributor role
- [ ] Add 4 secrets to GitHub repository
- [ ] Remove old STORAGE_CONNECTION_STRING secret
- [ ] Test workflow execution
- [ ] Verify blob uploads in Azure Portal
- [ ] Update local development environment (Azure CLI login)
- [ ] Document any custom environment-specific settings
- [ ] Monitor first few runs for issues

---

**Migration Date**: _____________  
**Performed By**: _____________  
**Verified By**: _____________
