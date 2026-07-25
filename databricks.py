import csv
import pandas as pd
from azure.identity import DefaultAzureCredential
from azure.mgmt.databricks import DatabricksClient

# Initialize Azure credentials and Databricks client
credential = DefaultAzureCredential()
subscription_id = "YOUR_SUBSCRIPTION_ID"  # Replace with your actual subscription ID
client = DatabricksClient(credential=credential, subscription_id=subscription_id)

def get_all_workspaces():
    """Retrieve all Databricks workspaces in the current subscription."""
    workspaces = []
    try:
        for workspace in client.workspaces.list_by_subscription():
            workspaces.append(workspace)
    except Exception as e:
        print(f"Error fetching workspaces: {e}")
    return workspaces

def extract_workspace_details(workspace):
    """Extract relevant details from a workspace object."""
    return {
        "name": workspace.name,
        "id": workspace.id,
        "location": workspace.location,
        "resource_group": workspace.id.split('/')[4] if workspace.id else None,
        "sku": workspace.sku.name if workspace.sku else None,
        "workspace_id": workspace.workspace_id,
        "workspace_url": workspace.workspace_url,  # This is the endpoint URL
        "provisioning_state": workspace.provisioning_state,
        "managed_resource_group_id": workspace.managed_resource_group_id,
        "created_date_time": workspace.created_date_time,
        "is_uc_enabled": workspace.is_uc_enabled,
        "tags": str(workspace.tags) if workspace.tags else None
    }

def save_to_csv(workspaces, filename="databricks_workspaces.csv"):
    """Save workspace details to a CSV file."""
    if not workspaces:
        print("No workspaces found.")
        return
    
    details_list = [extract_workspace_details(ws) for ws in workspaces]
    df = pd.DataFrame(details_list)
    
    df.to_csv(filename, index=False, encoding='utf-8')
    print(f"Successfully saved details of {len(df)} workspaces to {filename}")

def main():
    print("Fetching Databricks workspaces...")
    workspaces = get_all_workspaces()
    print(f"Found {len(workspaces)} workspaces.")
    
    save_to_csv(workspaces)
    
    # Optional: print a preview
    if workspaces:
        print("\nPreview of first 5 workspaces:")
        for i, ws in enumerate(workspaces[:5]):
            print(f"  {i+1}. {ws.name} -> {ws.workspace_url}")

if __name__ == "__main__":
    main()
