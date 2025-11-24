# 🔐 Azure Architecture Best Practices Audit
**Date:** November 24, 2025  
**Focus:** Azure Storage, Authentication, Security, Cost Optimization

---

## 📊 Executive Summary

| Category | Current Status | Best Practice Status | Priority |
|----------|---------------|---------------------|----------|
| **Authentication** | 🔴 CRITICAL | Connection Strings | HIGH |
| **Storage Security** | 🟡 NEEDS WORK | Public Access | HIGH |
| **Secrets Management** | 🟡 PARTIAL | Environment Variables | MEDIUM |
| **Cost Optimization** | 🟢 GOOD | Standard Tier | LOW |
| **Monitoring** | 🔴 MISSING | No Alerts | MEDIUM |
| **Backup/DR** | 🟡 PARTIAL | No Automation | MEDIUM |

**Overall:** 🔴 **SECURITY IMPROVEMENTS REQUIRED**

---

## 🚨 Critical Security Issues

### 1. **Using Connection Strings Instead of Managed Identity** ⚠️ HIGH PRIORITY

**Current Implementation:**
```python
# upload_newsletter_to_blob.py
connection_string = os.environ.get("STORAGE_CONNECTION_STRING")
blob_service_client = BlobServiceClient.from_connection_string(connection_string)
```

**Problems:**
- ❌ Connection strings are long-lived credentials (like passwords)
- ❌ If leaked, attacker has full storage account access
- ❌ No automatic rotation
- ❌ Hard to revoke/rotate without updating all services
- ❌ Stored as secrets in multiple places (GitHub, local)

**Azure Best Practice: Managed Identity**
```python
# RECOMMENDED APPROACH
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

# Automatically uses:
# - Azure Managed Identity (in Azure Functions/VMs)
# - Azure CLI credentials (local development)
# - Environment variables (CI/CD)
credential = DefaultAzureCredential()

storage_account_url = "https://yourstorageaccount.blob.core.windows.net"
blob_service_client = BlobServiceClient(storage_account_url, credential=credential)
```

**Benefits:**
- ✅ No secrets to manage
- ✅ Automatic credential rotation
- ✅ Scoped permissions (RBAC)
- ✅ Azure AD integration
- ✅ Audit logs in Azure Monitor

**Migration Steps:**

1. **Install Azure Identity SDK**
```txt
# Add to requirements.txt
azure-identity>=1.15.0
```

2. **Update Code**
```python
# scripts/upload_newsletter_to_blob.py
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

def upload_newsletter_to_blob(week_num: int, overwrite: bool = False) -> dict:
    # Use environment variable for local dev, Managed Identity in production
    storage_account_name = os.environ.get("AZURE_STORAGE_ACCOUNT", "yourstorageaccount")
    storage_account_url = f"https://{storage_account_name}.blob.core.windows.net"
    
    # DefaultAzureCredential automatically handles:
    # - Local: Azure CLI credentials
    # - GitHub Actions: Workload Identity or Service Principal
    # - Azure Functions: System-assigned Managed Identity
    credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(storage_account_url, credential=credential)
    
    # Rest of code unchanged...
```

3. **Configure Azure RBAC**
```bash
# Get your Azure identity (user, service principal, or managed identity)
IDENTITY_ID=$(az account show --query user.name -o tsv)

# Grant Storage Blob Data Contributor role
az role assignment create \
    --role "Storage Blob Data Contributor" \
    --assignee $IDENTITY_ID \
    --scope /subscriptions/{subscription-id}/resourceGroups/{rg}/providers/Microsoft.Storage/storageAccounts/{account}
```

4. **Update GitHub Actions**
```yaml
# .github/workflows/generate-newsletter-full.yml
- name: Azure Login
  uses: azure/login@v1
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

# No STORAGE_CONNECTION_STRING needed!
```

---

### 2. **Azure OpenAI Authentication** ✅ ACCEPTABLE (with improvements)

**Current Implementation:**
```python
# portfolio_automation.py
azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
client = AzureOpenAI(api_key=azure_api_key, ...)
```

**Status:** 🟡 **Acceptable but can be improved**

**Why API Keys are OK here:**
- Azure OpenAI supports Managed Identity (good!)
- But GitHub Actions can't easily use it
- API keys are scoped to one service (better than connection strings)

**Best Practice Improvements:**

1. **Add API Key Rotation Reminder**
```python
# Add to startup validation
API_KEY_AGE_DAYS = 90
def validate_api_key_age():
    """Remind to rotate API keys quarterly"""
    last_rotation = os.getenv("AZURE_OPENAI_KEY_ROTATION_DATE")
    if last_rotation:
        rotation_date = datetime.fromisoformat(last_rotation)
        days_old = (datetime.now() - rotation_date).days
        if days_old > API_KEY_AGE_DAYS:
            logging.warning(f"Azure OpenAI API key is {days_old} days old. Consider rotating.")
```

2. **Use Azure Key Vault for Production**
```python
# Optional: Retrieve secrets from Azure Key Vault
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def get_azure_openai_key():
    """Get API key from Azure Key Vault in production"""
    if os.getenv("AZURE_KEY_VAULT_NAME"):
        vault_url = f"https://{os.getenv('AZURE_KEY_VAULT_NAME')}.vault.azure.net"
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=credential)
        return client.get_secret("azure-openai-api-key").value
    else:
        # Fallback to environment variable for local dev
        return os.getenv("AZURE_OPENAI_API_KEY")
```

---

### 3. **Storage Account Public Access** 🔴 NEEDS VERIFICATION

**Current Risk:**
- Newsletter blobs in `newsletters` container - are they public?
- If public: anyone can read newsletters before they're sent
- If private: Azure Function might not have access

**Check Current Status:**
```bash
# Check if container allows public access
az storage container show-permission \
    --name newsletters \
    --account-name yourstorageaccount \
    --query publicAccess
```

**Best Practice:**
```bash
# Option 1: Private container + SAS tokens (recommended)
az storage container set-permission \
    --name newsletters \
    --public-access off \
    --account-name yourstorageaccount

# Option 2: Private container + Managed Identity (best)
# Already covered in Issue #1 above
```

**For Azure Function to Access:**
```python
# Azure Function should use Managed Identity
# Enable System-assigned Managed Identity for your Function App
# Grant it "Storage Blob Data Reader" role on newsletters container
```

---

## ⚠️ High Priority Improvements

### 4. **Missing Azure Monitor Alerts** 🔴 CRITICAL

**Current State:** No monitoring, alerts, or logging aggregation

**Issues:**
- Newsletter upload failures go unnoticed
- Azure Function errors not tracked
- No cost alerts for runaway API usage

**Recommended Azure Monitor Setup:**

```bash
# 1. Create Action Group (email notification)
az monitor action-group create \
    --name "portfolio-alerts" \
    --resource-group your-rg \
    --short-name "PfAlerts" \
    --email-receiver "Admin" "your-email@example.com"

# 2. Alert: Azure Function Failures
az monitor metrics alert create \
    --name "function-errors" \
    --resource-group your-rg \
    --scopes /subscriptions/.../providers/Microsoft.Web/sites/myblog-subscribers \
    --condition "count Http5xx > 5" \
    --window-size 5m \
    --evaluation-frequency 1m \
    --action portfolio-alerts

# 3. Alert: Storage Account High Costs
az monitor metrics alert create \
    --name "storage-cost-spike" \
    --resource-group your-rg \
    --scopes /subscriptions/.../providers/Microsoft.Storage/storageAccounts/yourAccount \
    --condition "total UsedCapacity > 10GB" \
    --window-size 1d

# 4. Alert: OpenAI API Quota
# (Set up in Azure Portal → Azure OpenAI → Quotas & Limits)
```

**Application Insights Integration:**
```python
# Add to requirements.txt
opencensus-ext-azure>=1.1.9

# Add to portfolio_automation.py
from opencensus.ext.azure.log_exporter import AzureLogHandler

# Add Azure Monitor instrumentation key
APPINSIGHTS_KEY = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if APPINSIGHTS_KEY:
    logger = logging.getLogger(__name__)
    logger.addHandler(AzureLogHandler(connection_string=APPINSIGHTS_KEY))
```

---

### 5. **No Backup/Disaster Recovery** 🟡 MEDIUM PRIORITY

**Current State:**
- ✅ Archive folder exists (`master data/archive/`)
- ❌ No automated backups
- ❌ No geo-redundancy
- ❌ No point-in-time restore

**Best Practices:**

1. **Enable Azure Blob Soft Delete**
```bash
# Protect against accidental deletion
az storage account blob-service-properties update \
    --account-name yourstorageaccount \
    --enable-delete-retention true \
    --delete-retention-days 30
```

2. **Enable Azure Blob Versioning**
```bash
# Keep version history of all blobs
az storage account blob-service-properties update \
    --account-name yourstorageaccount \
    --enable-versioning true
```

3. **Upgrade to GRS (Geo-Redundant Storage)**
```bash
# Current: LRS (Locally Redundant)
# Recommended: GRS (Geo-Redundant) for production
az storage account update \
    --name yourstorageaccount \
    --sku Standard_GRS
```

**Cost Impact:** ~2x storage cost, but provides:
- Cross-region replication
- 99.99999999999999% (16 9's) durability
- Disaster recovery capability

---

### 6. **Secrets in Multiple Places** 🟡 MEDIUM PRIORITY

**Current State:**
```
STORAGE_CONNECTION_STRING stored in:
├── Local .env file
├── GitHub Secrets
├── Azure Function App Settings
└── Potentially in shell history
```

**Issues:**
- Multiple copies = higher leak risk
- Hard to rotate (must update everywhere)
- No centralized audit trail

**Best Practice: Azure Key Vault**

```bash
# 1. Create Key Vault
az keyvault create \
    --name portfolio-vault \
    --resource-group your-rg \
    --location eastus

# 2. Store secrets
az keyvault secret set \
    --vault-name portfolio-vault \
    --name "azure-openai-key" \
    --value "your-key"

# 3. Grant access to Function App
az keyvault set-policy \
    --name portfolio-vault \
    --object-id $(az webapp identity show --name myblog-subscribers --resource-group your-rg --query principalId -o tsv) \
    --secret-permissions get list

# 4. Reference in Function App
# App Setting: @Microsoft.KeyVault(SecretUri=https://portfolio-vault.vault.azure.net/secrets/azure-openai-key/)
```

**Update Code:**
```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def get_secret(secret_name: str) -> str:
    """Get secret from Key Vault or fallback to env var"""
    vault_name = os.getenv("AZURE_KEY_VAULT_NAME")
    
    if vault_name:
        # Production: Use Key Vault
        credential = DefaultAzureCredential()
        client = SecretClient(f"https://{vault_name}.vault.azure.net", credential)
        return client.get_secret(secret_name).value
    else:
        # Local dev: Use environment variables
        return os.getenv(secret_name.upper().replace("-", "_"))
```

---

## ✅ What You're Doing Well

### 1. **Environment Variables (Not Hardcoded)** ✅
```python
azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")  # ✅ GOOD
connection_string = os.environ.get("STORAGE_CONNECTION_STRING")  # ✅ GOOD
```

### 2. **Fail-Fast on Missing Secrets** ✅
```python
if not azure_api_key:
    raise ValueError("AZURE_OPENAI_API_KEY environment variable not set")
```

### 3. **Using Standard Tier Storage** ✅
- Not using Premium (over-engineered)
- Not using Archive tier (too slow)
- Good balance of cost vs performance

### 4. **Blob Content-Type Headers** ✅
```python
content_settings=ContentSettings(content_type="text/html; charset=utf-8")
```

---

## 📋 Implementation Priority

### 🔴 Critical (Do First)
1. **Migrate to Managed Identity for Storage** (Security)
2. **Set up Azure Monitor Alerts** (Observability)
3. **Verify Storage Container Access Levels** (Security)

### 🟡 High Priority (Do Soon)
4. **Enable Blob Soft Delete & Versioning** (Data Protection)
5. **Centralize Secrets in Key Vault** (Security)
6. **Add Application Insights Logging** (Debugging)

### 🟢 Medium Priority (Nice to Have)
7. **Upgrade to GRS Storage** (Disaster Recovery)
8. **API Key Rotation Reminders** (Security)
9. **Cost Alerts** (Financial)

---

## 💰 Cost Impact Analysis

| Change | Current Cost | New Cost | Delta |
|--------|--------------|----------|-------|
| **Managed Identity** | $0 | $0 | Free! |
| **Azure Monitor** | $0 | ~$2/month | +$2 |
| **Key Vault** | $0 | ~$0.03/month | +$0.03 |
| **Blob Versioning** | $X | $X × 1.2 | +20% |
| **GRS Storage** | $X | $X × 2 | +100% |
| **Application Insights** | $0 | ~$2-5/month | +$2-5 |

**Total Monthly Impact:** ~$5-10/month for full best practices

---

## 🛠️ Quick Wins (Do Today)

### 1. Add Azure Identity Package
```bash
pip install azure-identity
# Add to requirements.txt
```

### 2. Create .env.example (Template)
```bash
# .env.example (commit this)
AZURE_STORAGE_ACCOUNT=your-storage-account-name
AZURE_KEY_VAULT_NAME=your-keyvault-name
AZURE_OPENAI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-5.1-chat
```

### 3. Enable Blob Soft Delete (5 minutes)
```bash
az storage account blob-service-properties update \
    --account-name yourstorageaccount \
    --enable-delete-retention true \
    --delete-retention-days 30
```

---

## 📚 Resources

- [Azure Storage Security Guide](https://learn.microsoft.com/azure/storage/common/storage-security-guide)
- [Managed Identity Best Practices](https://learn.microsoft.com/azure/active-directory/managed-identities-azure-resources/managed-identity-best-practice-recommendations)
- [Azure OpenAI Security](https://learn.microsoft.com/azure/ai-services/openai/how-to/managed-identity)
- [Azure Monitor Alerts](https://learn.microsoft.com/azure/azure-monitor/alerts/alerts-overview)

---

**Next Steps:** Review priorities with your team and create tickets for implementation.
