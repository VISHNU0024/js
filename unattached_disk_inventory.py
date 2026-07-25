#!/usr/bin/env python3
"""
Azure Unattached Disks Inventory Script
Fetches all managed disks from accessible Azure subscriptions and exports ONLY
UNATTACHED disks (those with managed_by = null) to a CSV file with all details.
"""

import csv
import argparse
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.subscription import SubscriptionClient


def get_all_subscriptions(credential):
    """Get a list of all subscription IDs the principal has access to."""
    subscription_client = SubscriptionClient(credential)
    subscriptions = []
    for sub in subscription_client.subscriptions.list():
        subscriptions.append(sub.subscription_id)
    return subscriptions


def get_disk_details(disk):
    """
    Extract all relevant details from a Disk object.
    Returns a flat dictionary with nested properties expanded.
    """
    # Basic top-level properties
    details = {
        'subscription_id': disk.id.split('/')[2] if disk.id else '',
        'resource_group': disk.id.split('/')[4] if disk.id else '',
        'name': disk.name,
        'location': disk.location,
        'type': disk.type,
        'managed_by': disk.managed_by,           # VM ID if attached, None if unattached
        'managed_by_extended': ', '.join(disk.managed_by_extended) if disk.managed_by_extended else '',
        'sku': disk.sku.name if disk.sku else '',
        'tier': disk.sku.tier if disk.sku and hasattr(disk.sku, 'tier') else '',
        'last_ownership_update_time': disk.last_ownership_update_time.isoformat() if disk.last_ownership_update_time else '',
    }
    
    # Nested properties (disk.properties)
    if disk.properties:
        props = disk.properties
        details.update({
            'disk_size_gb': props.disk_size_gb,
            'disk_state': props.disk_state,
            'provisioning_state': props.provisioning_state,
            'time_created': props.time_created.isoformat() if props.time_created else '',
            'os_type': props.os_type if hasattr(props, 'os_type') else '',
            'hyper_v_generation': props.hyper_v_generation if hasattr(props, 'hyper_v_generation') else '',
            'encryption_type': props.encryption.type if hasattr(props, 'encryption') and props.encryption else '',
            'network_access_policy': props.network_access_policy if hasattr(props, 'network_access_policy') else '',
            'public_network_access': props.public_network_access if hasattr(props, 'public_network_access') else '',
            'supported_capabilities': ', '.join(props.supported_capabilities) if hasattr(props, 'supported_capabilities') and props.supported_capabilities else '',
            'disk_iops_read_write': props.disk_iops_read_write if hasattr(props, 'disk_iops_read_write') else '',
            'disk_mbps_read_write': props.disk_mbps_read_write if hasattr(props, 'disk_mbps_read_write') else '',
            'max_shares': props.max_shares if hasattr(props, 'max_shares') else '',
            'creation_data_source': props.creation_data.source_uri if hasattr(props, 'creation_data') and props.creation_data else '',
        })
    else:
        details.update({
            'disk_size_gb': '',
            'disk_state': '',
            'provisioning_state': '',
            'time_created': '',
            'os_type': '',
            'hyper_v_generation': '',
            'encryption_type': '',
            'network_access_policy': '',
            'public_network_access': '',
            'supported_capabilities': '',
            'disk_iops_read_write': '',
            'disk_mbps_read_write': '',
            'max_shares': '',
            'creation_data_source': '',
        })
    
    details['tags'] = ', '.join([f"{k}={v}" for k, v in disk.tags.items()]) if disk.tags else ''
    details['zones'] = ', '.join(disk.zones) if disk.zones else ''
    details['extended_location'] = disk.extended_location.name if disk.extended_location else ''
    
    return details


def main():
    parser = argparse.ArgumentParser(
        description='Export ONLY UNATTACHED Azure Managed Disks to CSV with all details'
    )
    parser.add_argument('--output', '-o', default='unattached_disks_inventory.csv',
                        help='Output CSV filename (default: unattached_disks_inventory.csv)')
    parser.add_argument('--subscription', '-s', help='Specific subscription ID (optional; defaults to all accessible)')
    parser.add_argument('--inactive-days', '-i', type=int, default=30,
                        help='Flag disks as "inactive" if no ownership change in this many days (default: 30)')
    args = parser.parse_args()
    
    print("🔐 Authenticating to Azure...")
    credential = DefaultAzureCredential()
    
    if args.subscription:
        subscriptions = [args.subscription]
        print(f"📋 Using subscription: {args.subscription}")
    else:
        subscriptions = get_all_subscriptions(credential)
        print(f"📋 Found {len(subscriptions)} accessible subscription(s)")
    
    all_disks = []          # We'll collect all disks first
    cutoff_date = datetime.utcnow() - timedelta(days=args.inactive_days)
    
    for sub_id in subscriptions:
        print(f"🔄 Processing subscription: {sub_id}")
        try:
            compute_client = ComputeManagementClient(credential, sub_id)
            disks = compute_client.disks.list()
            
            count = 0
            for disk in disks:
                details = get_disk_details(disk)
                details['subscription_id'] = sub_id
                
                # Calculate inactivity flag based on last ownership update
                last_update = details.get('last_ownership_update_time')
                if last_update:
                    try:
                        last_update_dt = datetime.fromisoformat(last_update)
                        details['inactive_since_days'] = (datetime.utcnow() - last_update_dt).days
                        details['is_inactive'] = details['inactive_since_days'] > args.inactive_days
                    except (ValueError, TypeError):
                        details['inactive_since_days'] = ''
                        details['is_inactive'] = ''
                else:
                    details['inactive_since_days'] = ''
                    details['is_inactive'] = ''
                
                all_disks.append(details)
                count += 1
            
            print(f"   ✅ Found {count} disk(s) in this subscription")
            
        except Exception as e:
            print(f"   ❌ Error processing subscription {sub_id}: {str(e)}")
    
    print(f"\n📊 Total disks found (all subscriptions): {len(all_disks)}")
    
    # ----- FILTER: Keep only unattached disks (managed_by is None or empty) -----
    unattached_disks = [d for d in all_disks if not d.get('managed_by')]
    print(f"   Unattached disks found: {len(unattached_disks)}")
    
    if not unattached_disks:
        print("⚠️  No unattached disks found. Exiting without creating CSV.")
        return
    
    # Define the CSV column order
    fieldnames = [
        'subscription_id',
        'resource_group',
        'name',
        'location',
        'type',
        'managed_by',                # Will be empty for all records in this CSV
        'managed_by_extended',
        'sku',
        'tier',
        'disk_size_gb',
        'disk_state',
        'provisioning_state',
        'time_created',
        'os_type',
        'hyper_v_generation',
        'encryption_type',
        'network_access_policy',
        'public_network_access',
        'supported_capabilities',
        'disk_iops_read_write',
        'disk_mbps_read_write',
        'max_shares',
        'creation_data_source',
        'tags',
        'zones',
        'extended_location',
        'last_ownership_update_time',
        'inactive_since_days',
        'is_inactive',
    ]
    
    # Write only unattached disks to the CSV
    output_file = args.output
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(unattached_disks)
    
    print(f"✅ CSV exported successfully to: {output_file}")
    print(f"   Total rows (unattached disks): {len(unattached_disks)}")
    
    # Additional summary for unattached disks
    inactive_unattached = [d for d in unattached_disks if d.get('is_inactive') == True]
    print(f"   Unattached disks with no ownership change in >{args.inactive_days} days: {len(inactive_unattached)}")
    
    print("\n⚠️  NOTE: 'last_ownership_update_time' is the LAST ATTACH/DETACH time.")
    print("   Azure does NOT provide 'last read' or 'last write' timestamps for disks.")


if __name__ == '__main__':
    main()
