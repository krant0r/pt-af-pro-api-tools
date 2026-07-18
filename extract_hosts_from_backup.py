#!/usr/bin/env python3
"""
Script to extract FQDN hosts from PTAF backup archives.
Backup structure:
  - backup.tar (or .tar.lzma)
    - TENANTS (tar archive with PostgreSQL dump)
    - SECURITY_CONFIGURATION (tar archive with confmanager dump)
      - schema.tar (contains restore.sql and toc.dat)
      - data.tar (contains *.dat files with table data)
        - host_locations data in specific .dat file
"""

import tarfile
import os
import sys
import re
import tempfile
import shutil
from pathlib import Path


def extract_tar(archive_path, extract_to):
    """Extract tar archive."""
    try:
        with tarfile.open(archive_path, 'r:*') as tar:
            tar.extractall(path=extract_to)
        return True
    except Exception as e:
        print(f"Error extracting {archive_path}: {e}")
        return False


def extract_lzma(archive_path, extract_to):
    """Extract .tar.lzma archive using subprocess."""
    import subprocess
    try:
        # Use system tar command which supports lzma
        subprocess.run(
            ['tar', '-xf', archive_path, '-C', extract_to],
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error extracting LZMA {archive_path}: {e.stderr.decode() if e.stderr else e}")
        return False
    except FileNotFoundError:
        print("tar command not found. Please install GNU tar.")
        return False


def find_host_locations_file(toc_path, restore_sql_path=None):
    """Find the .dat file containing host_locations data from toc.dat or restore.sql."""
    # Try restore.sql first - it has clearer format
    if restore_sql_path and restore_sql_path.exists():
        try:
            with open(restore_sql_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if 'COPY public.host_locations' in line and '$$PATH$$' in line:
                        match = re.search(r'\$\$PATH\$\$/(\d+\.dat)', line)
                        if match:
                            return match.group(1)
        except Exception as e:
            print(f"Error reading restore.sql: {e}")
    
    # Fallback to toc.dat
    try:
        with open(toc_path, 'rb') as f:
            content = f.read().decode('utf-8', errors='ignore')
        
        # Look for pattern like "4036.dat" or "4070.dat" after host_locations
        matches = re.findall(r'host_locations.*?(\d+\.dat)', content)
        if matches:
            return matches[0]
            
    except Exception as e:
        print(f"Error reading toc.dat: {e}")
    return None


def extract_hosts_from_dat(dat_path):
    """Extract FQDN hosts from .dat file."""
    hosts = set()
    try:
        with open(dat_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line == '\\.' or line == '' or line.startswith('--'):
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 2:
                    host = parts[1]
                    # Skip NULL values and invalid entries
                    if host and host != r'\N' and not host.startswith(r'\.'):
                        # Validate FQDN pattern (basic check)
                        if re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$', host):
                            hosts.add(host)
    except Exception as e:
        print(f"Error reading {dat_path}: {e}")
    
    return sorted(hosts)


def extract_backup(backup_path):
    """Main function to extract hosts from backup."""
    backup_path = Path(backup_path)
    
    if not backup_path.exists():
        print(f"Backup file not found: {backup_path}")
        return []
    
    # Create temporary directory for extraction
    temp_dir = tempfile.mkdtemp(prefix='backup_extract_')
    
    try:
        # Step 1: Extract main backup archive
        print(f"Extracting main backup: {backup_path}")
        
        if backup_path.suffix == '.lzma':
            extract_lzma(str(backup_path), temp_dir)
        else:
            extract_tar(str(backup_path), temp_dir)
        
        # Step 1.5: Check if there's a nested backup.tar.lzma
        nested_backup = Path(temp_dir) / 'backup.tar.lzma'
        if nested_backup.exists():
            print(f"Found nested backup: backup.tar.lzma")
            nested_dir = Path(temp_dir) / 'nested'
            nested_dir.mkdir(exist_ok=True)
            extract_lzma(str(nested_backup), str(nested_dir))
            # Move contents up
            for item in nested_dir.iterdir():
                dest = Path(temp_dir) / item.name
                if dest.exists():
                    # Keep original if exists
                    continue
                shutil.move(str(item), str(dest))
            # Remove nested dir
            shutil.rmtree(nested_dir, ignore_errors=True)
            # Remove the lzma file
            nested_backup.unlink()
        
        # Step 2: Find and extract TENANTS or SECURITY_CONFIGURATION
        # SECURITY_CONFIGURATION might be a file (tar archive without extension) or directory
        security_config = Path(temp_dir) / 'SECURITY_CONFIGURATION'
        
        if security_config.is_file():
            # It's a tar archive - extract it
            print("SECURITY_CONFIGURATION is a file, extracting...")
            sec_dir = Path(temp_dir) / 'sec_extracted'
            sec_dir.mkdir(exist_ok=True)
            extract_tar(str(security_config), str(sec_dir))
            security_config = sec_dir
        elif not security_config.exists():
            # Try to find it as a file (might be named differently)
            for item in Path(temp_dir).iterdir():
                if item.is_file() and 'SECURITY' in item.name.upper():
                    sec_dir = Path(temp_dir) / 'sec_extracted'
                    sec_dir.mkdir(exist_ok=True)
                    extract_tar(str(item), str(sec_dir))
                    # Look for SECURITY_CONFIGURATION inside
                    for subitem in sec_dir.iterdir():
                        if 'SECURITY' in subitem.name.upper():
                            security_config = subitem
                            break
                    break
        
        if not security_config.exists() and not security_config.is_dir():
            print("SECURITY_CONFIGURATION not found in backup")
            print(f"Contents of temp dir: {list(Path(temp_dir).iterdir())}")
            return []
        
        # Step 3: Extract schema.tar and data.tar from SECURITY_CONFIGURATION
        schema_tar = security_config / 'schema.tar'
        data_tar = security_config / 'data.tar'
        
        schema_dir = Path(temp_dir) / 'schema'
        data_dir = Path(temp_dir) / 'data'
        
        schema_dir.mkdir(exist_ok=True)
        data_dir.mkdir(exist_ok=True)
        
        if schema_tar.exists():
            print(f"Extracting schema.tar")
            extract_tar(str(schema_tar), str(schema_dir))
        
        if data_tar.exists():
            print(f"Extracting data.tar")
            extract_tar(str(data_tar), str(data_dir))
        
        # Step 4: Find host_locations .dat file
        toc_path = data_dir / 'toc.dat'
        restore_sql_path = data_dir / 'restore.sql'
        
        if toc_path.exists():
            dat_file = find_host_locations_file(toc_path, restore_sql_path)
            if dat_file:
                dat_path = data_dir / dat_file
                if dat_path.exists():
                    print(f"Found host_locations data in: {dat_file}")
                    hosts = extract_hosts_from_dat(str(dat_path))
                    return hosts
                else:
                    print(f"Data file {dat_file} not found")
            else:
                print("Could not find host_locations file in toc.dat")
        else:
            print("toc.dat not found")
        
        return []
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_hosts.py <backup_file>")
        print("  Supports .tar and .tar.lzma backup files")
        sys.exit(1)
    
    backup_file = sys.argv[1]
    
    print(f"Processing backup: {backup_file}")
    print("=" * 60)
    
    hosts = extract_backup(backup_file)
    
    print("\n" + "=" * 60)
    if hosts:
        print(f"Found {len(hosts)} unique FQDN hosts:")
        print("=" * 60)
        for host in hosts:
            print(host)
    else:
        print("No hosts found in backup")
        sys.exit(1)


if __name__ == '__main__':
    main()