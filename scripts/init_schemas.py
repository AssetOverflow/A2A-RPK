#!/usr/bin/env python3
"""
Comprehensive Redpanda Schema Registry Management Script
Implements all Redpanda Schema Registry API endpoints for production use.

Features:
- Schema registration and retrieval
- Compatibility configuration and validation
- Version management and evolution tracking
- Schema deletion (soft/hard) and cleanup
- Mode configuration (READONLY/READWRITE)
- Schema references and dependencies
- Health monitoring and diagnostics
- Export/import capabilities
"""

import json
import requests
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from enum import Enum

class CompatibilityLevel(Enum):
    """Schema Registry compatibility levels"""
    BACKWARD = "BACKWARD"
    BACKWARD_TRANSITIVE = "BACKWARD_TRANSITIVE"
    FORWARD = "FORWARD"
    FORWARD_TRANSITIVE = "FORWARD_TRANSITIVE"
    FULL = "FULL"
    FULL_TRANSITIVE = "FULL_TRANSITIVE"
    NONE = "NONE"

class RegistryMode(Enum):
    """Schema Registry operation modes"""
    READONLY = "READONLY"
    READWRITE = "READWRITE"

class SchemaType(Enum):
    """Supported schema types"""
    AVRO = "AVRO"
    JSON = "JSON"
    PROTOBUF = "PROTOBUF"

class RegistryManager:
    """
    Comprehensive Redpanda Schema Registry Manager
    Implements all Schema Registry API endpoints for production use
    """
    
    def __init__(self, base_uri: str = "http://localhost:18081", timeout: int = 30):
        """
        Initialize the Registry Manager
        
        Args:
            base_uri: Schema Registry base URL (default matches Redpanda docs)
            timeout: Request timeout in seconds
        """
        self.base_uri = base_uri.rstrip('/')
        self.timeout = timeout
        self.schemas_dir = Path(__file__).parent.parent / "schemas"
        
        # Configure session with proper headers
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/vnd.schemaregistry.v1+json",
            "Accept": "application/vnd.schemaregistry.v1+json"
        })
        
        # Helper function for pretty printing (as shown in docs)
        self.pretty = lambda text: print(json.dumps(text, indent=2))
    
    # === CORE API ENDPOINTS ===
    
    def query_supported_formats(self) -> List[str]:
        """
        Query supported schema formats
        GET /schemas/types
        """
        try:
            response = self.session.get(f'{self.base_uri}/schemas/types', timeout=self.timeout)
            if response.status_code == 200:
                formats = response.json()
                print(f"✅ Supported formats: {formats}")
                return formats
            else:
                print(f"❌ Failed to query formats: HTTP {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error querying formats: {e}")
            return []
    
    def register_schema(self, subject: str, schema: Dict, schema_type: SchemaType = SchemaType.AVRO) -> Optional[Dict]:
        """
        Register a schema for a subject
        POST /subjects/{subject}/versions
        """
        try:
            payload = {
                'schema': json.dumps(schema)
            }
            
            # Add schema type if not AVRO (AVRO is default)
            if schema_type != SchemaType.AVRO:
                payload['schemaType'] = schema_type.value
            
            response = self.session.post(
                url=f'{self.base_uri}/subjects/{subject}/versions',
                data=json.dumps(payload),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Registered schema '{subject}': ID {result.get('id')}, Version {result.get('version', 'N/A')}")
                return result
            elif response.status_code == 409:
                print(f"ℹ️  Schema '{subject}' already exists (identical schema)")
                return {"status": "exists"}
            else:
                print(f"❌ Failed to register '{subject}': HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error registering schema '{subject}': {e}")
            return None
    
    def retrieve_schema_by_id(self, schema_id: int) -> Optional[Dict]:
        """
        Retrieve a schema by its ID
        GET /schemas/ids/{id}
        """
        try:
            response = self.session.get(f'{self.base_uri}/schemas/ids/{schema_id}', timeout=self.timeout)
            if response.status_code == 200:
                schema_data = response.json()
                print(f"✅ Retrieved schema ID {schema_id}")
                return schema_data
            else:
                print(f"❌ Failed to retrieve schema ID {schema_id}: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error retrieving schema ID {schema_id}: {e}")
            return None
    
    def list_subjects(self, include_deleted: bool = False) -> List[str]:
        """
        List all registry subjects
        GET /subjects[?deleted=true]
        """
        try:
            params = {'deleted': 'true'} if include_deleted else {}
            response = self.session.get(f'{self.base_uri}/subjects', params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                subjects = response.json()
                deleted_msg = " (including deleted)" if include_deleted else ""
                print(f"✅ Found {len(subjects)} subjects{deleted_msg}: {subjects}")
                return subjects
            else:
                print(f"❌ Failed to list subjects: HTTP {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error listing subjects: {e}")
            return []
    
    def get_subject_versions(self, subject: str) -> List[int]:
        """
        Retrieve schema versions of a subject
        GET /subjects/{subject}/versions
        """
        try:
            response = self.session.get(f'{self.base_uri}/subjects/{subject}/versions', timeout=self.timeout)
            if response.status_code == 200:
                versions = response.json()
                print(f"✅ Subject '{subject}' has versions: {versions}")
                return versions
            else:
                print(f"❌ Failed to get versions for '{subject}': HTTP {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error getting versions for '{subject}': {e}")
            return []
    
    def get_subject_schema(self, subject: str, version: Union[int, str] = "latest") -> Optional[Dict]:
        """
        Retrieve a schema of a subject
        GET /subjects/{subject}/versions/{version}
        """
        try:
            response = self.session.get(
                f'{self.base_uri}/subjects/{subject}/versions/{version}', 
                timeout=self.timeout
            )
            if response.status_code == 200:
                schema_data = response.json()
                print(f"✅ Retrieved schema for '{subject}' version {version}")
                return schema_data
            else:
                print(f"❌ Failed to get schema for '{subject}' v{version}: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error getting schema for '{subject}' v{version}: {e}")
            return None
    
    def get_subject_schema_only(self, subject: str, version: Union[int, str] = "latest") -> Optional[Dict]:
        """
        Retrieve only the schema content (without metadata)
        GET /subjects/{subject}/versions/{version}/schema
        """
        try:
            response = self.session.get(
                f'{self.base_uri}/subjects/{subject}/versions/{version}/schema', 
                timeout=self.timeout
            )
            if response.status_code == 200:
                schema = response.json()
                print(f"✅ Retrieved schema content for '{subject}' version {version}")
                return schema
            else:
                print(f"❌ Failed to get schema content for '{subject}' v{version}: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error getting schema content for '{subject}' v{version}: {e}")
            return None
    
    # === COMPATIBILITY CONFIGURATION ===
    
    def get_global_compatibility(self) -> Optional[str]:
        """
        Get global compatibility configuration
        GET /config
        """
        try:
            response = self.session.get(f'{self.base_uri}/config', timeout=self.timeout)
            if response.status_code == 200:
                config = response.json()
                compatibility = config.get('compatibilityLevel', 'UNKNOWN')
                print(f"✅ Global compatibility level: {compatibility}")
                return compatibility
            else:
                print(f"❌ Failed to get global config: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error getting global config: {e}")
            return None
    
    def set_global_compatibility(self, level: CompatibilityLevel) -> bool:
        """
        Set global compatibility level
        PUT /config
        """
        try:
            payload = {'compatibility': level.value}
            response = self.session.put(
                f'{self.base_uri}/config',
                data=json.dumps(payload),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Set global compatibility to: {result.get('compatibility')}")
                return True
            else:
                print(f"❌ Failed to set global compatibility: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error setting global compatibility: {e}")
            return False
    
    def get_subject_compatibility(self, subject: str) -> Optional[str]:
        """
        Get subject-specific compatibility configuration
        GET /config/{subject}
        """
        try:
            response = self.session.get(f'{self.base_uri}/config/{subject}', timeout=self.timeout)
            if response.status_code == 200:
                config = response.json()
                compatibility = config.get('compatibilityLevel')
                print(f"✅ Subject '{subject}' compatibility: {compatibility}")
                return compatibility
            elif response.status_code == 404:
                print(f"ℹ️  Subject '{subject}' uses global compatibility settings")
                return None
            else:
                print(f"❌ Failed to get config for '{subject}': HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error getting config for '{subject}': {e}")
            return None
    
    def set_subject_compatibility(self, subject: str, level: CompatibilityLevel) -> bool:
        """
        Set subject-specific compatibility level
        PUT /config/{subject}
        """
        try:
            payload = {'compatibility': level.value}
            response = self.session.put(
                f'{self.base_uri}/config/{subject}',
                data=json.dumps(payload),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Set '{subject}' compatibility to: {result.get('compatibility')}")
                return True
            else:
                print(f"❌ Failed to set compatibility for '{subject}': HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error setting compatibility for '{subject}': {e}")
            return False
    
    def test_compatibility(self, subject: str, schema: Dict, version: Union[int, str] = "latest") -> bool:
        """
        Test schema compatibility against a specific version
        POST /compatibility/subjects/{subject}/versions/{version}
        """
        try:
            payload = {'schema': json.dumps(schema)}
            response = self.session.post(
                f'{self.base_uri}/compatibility/subjects/{subject}/versions/{version}',
                data=json.dumps(payload),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                is_compatible = result.get('is_compatible', False)
                if is_compatible:
                    print(f"✅ Schema is compatible with '{subject}' v{version}")
                else:
                    print(f"❌ Schema is NOT compatible with '{subject}' v{version}")
                    if 'messages' in result:
                        for msg in result['messages']:
                            print(f"   - {msg}")
                return is_compatible
            else:
                print(f"❌ Failed to test compatibility: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error testing compatibility: {e}")
            return False
    
    # === SCHEMA DELETION ===
    
    def soft_delete_schema(self, subject: str, version: Union[int, str]) -> bool:
        """
        Soft delete a schema version
        DELETE /subjects/{subject}/versions/{version}
        """
        try:
            response = self.session.delete(
                f'{self.base_uri}/subjects/{subject}/versions/{version}',
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                deleted_version = response.json()
                print(f"✅ Soft deleted '{subject}' version {version} (can be restored)")
                return True
            else:
                print(f"❌ Failed to soft delete '{subject}' v{version}: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error soft deleting '{subject}' v{version}: {e}")
            return False
    
    def hard_delete_schema(self, subject: str, version: Union[int, str]) -> bool:
        """
        Hard delete a schema version (permanent)
        DELETE /subjects/{subject}/versions/{version}?permanent=true
        """
        try:
            # First soft delete
            if not self.soft_delete_schema(subject, version):
                return False
            
            # Then hard delete
            params = {'permanent': 'true'}
            response = self.session.delete(
                f'{self.base_uri}/subjects/{subject}/versions/{version}',
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                print(f"✅ Hard deleted '{subject}' version {version} (PERMANENT)")
                return True
            else:
                print(f"❌ Failed to hard delete '{subject}' v{version}: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error hard deleting '{subject}' v{version}: {e}")
            return False
    
    def delete_subject(self, subject: str, permanent: bool = False) -> bool:
        """
        Delete all versions of a subject
        DELETE /subjects/{subject}[?permanent=true]
        """
        try:
            params = {'permanent': 'true'} if permanent else {}
            response = self.session.delete(
                f'{self.base_uri}/subjects/{subject}',
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                versions = response.json()
                delete_type = "hard" if permanent else "soft"
                print(f"✅ {delete_type.title()} deleted subject '{subject}' (versions: {versions})")
                return True
            else:
                print(f"❌ Failed to delete subject '{subject}': HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error deleting subject '{subject}': {e}")
            return False
    
    # === SCHEMA REFERENCES ===
    
    def get_schema_references(self, subject: str, version: Union[int, str]) -> List[Dict]:
        """
        Get schemas that reference this schema
        GET /subjects/{subject}/versions/{version}/referencedby
        """
        try:
            response = self.session.get(
                f'{self.base_uri}/subjects/{subject}/versions/{version}/referencedby',
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                references = response.json()
                print(f"✅ Schema '{subject}' v{version} is referenced by: {len(references)} schemas")
                return references
            else:
                print(f"❌ Failed to get references for '{subject}' v{version}: HTTP {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error getting references for '{subject}' v{version}: {e}")
            return []
    
    # === MODE CONFIGURATION (READONLY/READWRITE) ===
    
    def get_global_mode(self) -> Optional[str]:
        """
        Get global mode
        GET /mode
        """
        try:
            response = self.session.get(f'{self.base_uri}/mode', timeout=self.timeout)
            if response.status_code == 200:
                mode_data = response.json()
                mode = mode_data.get('mode', 'UNKNOWN')
                print(f"✅ Global mode: {mode}")
                return mode
            else:
                print(f"❌ Failed to get global mode: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error getting global mode: {e}")
            return None
    
    def set_global_mode(self, mode: RegistryMode) -> bool:
        """
        Set global mode
        PUT /mode
        """
        try:
            payload = {'mode': mode.value}
            response = self.session.put(
                f'{self.base_uri}/mode',
                data=json.dumps(payload),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Set global mode to: {result.get('mode')}")
                return True
            else:
                print(f"❌ Failed to set global mode: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error setting global mode: {e}")
            return False
    
    def get_subject_mode(self, subject: str, default_to_global: bool = True) -> Optional[str]:
        """
        Get mode for a subject
        GET /mode/{subject}[?defaultToGlobal=true]
        """
        try:
            params = {'defaultToGlobal': 'true'} if default_to_global else {}
            response = self.session.get(
                f'{self.base_uri}/mode/{subject}',
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                mode_data = response.json()
                mode = mode_data.get('mode')
                print(f"✅ Subject '{subject}' mode: {mode}")
                return mode
            elif response.status_code == 404 and not default_to_global:
                print(f"ℹ️  Subject '{subject}' has no specific mode set")
                return None
            else:
                print(f"❌ Failed to get mode for '{subject}': HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error getting mode for '{subject}': {e}")
            return None
    
    def set_subject_mode(self, subject: str, mode: RegistryMode) -> bool:
        """
        Set mode for a subject
        PUT /mode/{subject}
        """
        try:
            payload = {'mode': mode.value}
            response = self.session.put(
                f'{self.base_uri}/mode/{subject}',
                data=json.dumps(payload),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Set mode for '{subject}' to: {result.get('mode')}")
                return True
            else:
                print(f"❌ Failed to set mode for '{subject}': HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error setting mode for '{subject}': {e}")
            return False
    
    # === UTILITY METHODS FOR A2A PROJECT ===
    
    def wait_for_registry(self, max_retries: int = 10, retry_delay: int = 3) -> bool:
        """Wait for Schema Registry to become available"""
        print(f"⏳ Waiting for Schema Registry at {self.base_uri}...")
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(f"{self.base_uri}/config", timeout=5)
                if response.status_code == 200:
                    print("✅ Schema Registry is available")
                    return True
                    
            except requests.exceptions.RequestException:
                pass
                
            if attempt < max_retries - 1:
                print(f"⏳ Attempt {attempt + 1}/{max_retries} failed, retrying in {retry_delay}s...")
                time.sleep(retry_delay)
        
        print("❌ Schema Registry is not available after maximum retries")
        return False
    
    def check_registry_health(self) -> bool:
        """Check if Schema Registry is accessible and healthy"""
        try:
            # Check basic connectivity
            response = self.session.get(f"{self.base_uri}/subjects", timeout=5)
            if response.status_code != 200:
                print(f"❌ Schema Registry health check failed: HTTP {response.status_code}")
                return False
            
            # Check config endpoint
            config_response = self.session.get(f"{self.base_uri}/config", timeout=5)
            if config_response.status_code != 200:
                print(f"❌ Schema Registry config endpoint failed: HTTP {config_response.status_code}")
                return False
            
            print("✅ Schema Registry is healthy")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to Schema Registry: {e}")
            return False
    
    def load_schema_file(self, schema_file: Path) -> Dict:
        """Load and validate an Avro schema file"""
        try:
            with open(schema_file, 'r') as f:
                schema = json.load(f)
            
            # Basic Avro schema validation
            if not isinstance(schema, dict):
                raise ValueError("Schema must be a JSON object")
            
            if "name" not in schema and "type" not in schema:
                raise ValueError("Schema must have 'name' or 'type' field")
            
            print(f"✅ Loaded schema: {schema_file.name}")
            return schema
            
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {schema_file.name}: {e}")
            raise
        except Exception as e:
            print(f"❌ Error loading {schema_file.name}: {e}")
            raise
    
    def get_detailed_subject_info(self, subject: str) -> Dict:
        """Get comprehensive information about a subject"""
        info = {
            "subject": subject,
            "versions": [],
            "latest_version": None,
            "compatibility": None,
            "schemas": []
        }
        
        try:
            # Get versions
            versions = self.get_subject_versions(subject)
            info["versions"] = versions
            
            if versions:
                # Get latest version details
                latest = self.get_subject_schema(subject, "latest")
                info["latest_version"] = latest
                
                # Get compatibility config
                compatibility = self.get_subject_compatibility(subject)
                info["compatibility"] = compatibility if compatibility else "GLOBAL"
                
                # Get schema details for each version
                for version in versions[-3:]:  # Last 3 versions
                    schema_info = self.get_subject_schema(subject, version)
                    if schema_info:
                        info["schemas"].append({
                            "version": version,
                            "id": schema_info.get("id"),
                            "schema": schema_info.get("schema")
                        })
        
        except Exception as e:
            print(f"❌ Error getting detailed info for '{subject}': {e}")
        
        return info
    
    def setup_a2a_compatibility_policies(self) -> bool:
        """Set up recommended compatibility policies for A2A messaging"""
        print("🔧 Setting up A2A compatibility policies...")
        
        # Set global default to BACKWARD for safe evolution
        if not self.set_global_compatibility(CompatibilityLevel.BACKWARD):
            return False
        
        # Set specific policies for each subject type
        subject_policies = {
            "task-requests-value": CompatibilityLevel.FORWARD,  # Producers should be compatible
            "task-responses-value": CompatibilityLevel.BACKWARD,  # Consumers should be compatible
            "negotiations-value": CompatibilityLevel.FULL  # Bidirectional compatibility
        }
        
        success = True
        for subject, policy in subject_policies.items():
            if not self.set_subject_compatibility(subject, policy):
                success = False
        
        return success
    
    def register_a2a_schemas(self, check_compatibility: bool = True, setup_policies: bool = True) -> bool:
        """Register all A2A schemas from the schemas directory"""
        print("🚀 Starting A2A schema registration...")
        
        # Wait for registry to be available
        if not self.wait_for_registry():
            return False
        
        # Check registry health
        if not self.check_registry_health():
            return False
        
        # Get initial global config
        self.get_global_compatibility()
        
        # Set up compatibility policies if requested
        if setup_policies:
            if not self.setup_a2a_compatibility_policies():
                print("⚠️  Failed to setup compatibility policies, continuing...")
        
        # Schema file to subject mapping with metadata
        schema_mappings = {
            "task_request.avsc": {
                "subject": "task-requests-value",
                "description": "Schema for task request messages",
                "compatibility": CompatibilityLevel.FORWARD
            },
            "task_response.avsc": {
                "subject": "task-responses-value", 
                "description": "Schema for task response messages",
                "compatibility": CompatibilityLevel.BACKWARD
            },
            "negotiation_message.avsc": {
                "subject": "negotiations-value",
                "description": "Schema for negotiation messages",
                "compatibility": CompatibilityLevel.FULL
            }
        }
        
        success_count = 0
        total_count = len(schema_mappings)
        registration_results = {}
        
        for schema_file, metadata in schema_mappings.items():
            schema_path = self.schemas_dir / schema_file
            subject = metadata["subject"]
            
            print(f"\n📝 Processing {schema_file} -> {subject}")
            print(f"   Description: {metadata['description']}")
            
            if not schema_path.exists():
                print(f"⚠️  Schema file not found: {schema_path}")
                registration_results[subject] = {"status": "file_not_found", "schema_id": None}
                continue
            
            try:
                # Load the schema
                schema = self.load_schema_file(schema_path)
                
                # Test compatibility if requested and subject exists
                if check_compatibility:
                    versions = self.get_subject_versions(subject)
                    if versions:
                        if not self.test_compatibility(subject, schema):
                            print(f"❌ Schema compatibility check failed for '{subject}'")
                            registration_results[subject] = {"status": "compatibility_failed", "schema_id": None}
                            continue
                
                # Register with Schema Registry
                result = self.register_schema(subject, schema)
                
                if result and result.get("id"):
                    success_count += 1
                    registration_results[subject] = {"status": "success", "schema_id": result.get("id")}
                elif result and result.get("status") == "exists":
                    success_count += 1
                    registration_results[subject] = {"status": "already_exists", "schema_id": None}
                else:
                    registration_results[subject] = {"status": "failed", "schema_id": None}
                    
            except Exception as e:
                print(f"❌ Failed to process {schema_file}: {e}")
                registration_results[subject] = {"status": "error", "schema_id": None, "error": str(e)}
        
        # Print summary
        print(f"\n📊 A2A schema registration summary:")
        print(f"   ✅ Successful: {success_count}/{total_count}")
        print(f"   ❌ Failed: {total_count - success_count}/{total_count}")
        
        for subject, result in registration_results.items():
            status_emoji = "✅" if result["status"] in ["success", "already_exists"] else "❌"
            print(f"   {status_emoji} {subject}: {result['status']}")
            if result.get("schema_id"):
                print(f"      Schema ID: {result['schema_id']}")
        
        if success_count == total_count:
            print("\n🎉 All A2A schemas registered successfully!")
            return True
        else:
            print("\n⚠️  Some A2A schemas failed to register")
            return False
    
    def verify_a2a_schemas(self, detailed: bool = True) -> bool:
        """Verify all A2A schemas are properly registered with detailed analysis"""
        print("\n🔍 Verifying A2A schema registration...")
        
        expected_subjects = [
            "task-requests-value",
            "task-responses-value", 
            "negotiations-value"
        ]
        
        registered_subjects = self.list_subjects()
        
        missing_subjects = [s for s in expected_subjects if s not in registered_subjects]
        
        if missing_subjects:
            print(f"❌ Missing A2A schemas: {missing_subjects}")
            return False
        
        print("✅ All expected A2A schemas are registered")
        
        if detailed:
            print("\n📋 Detailed A2A schema information:")
            for subject in expected_subjects:
                try:
                    info = self.get_detailed_subject_info(subject)
                    print(f"\n🔸 {subject}:")
                    print(f"   Versions: {info['versions']}")
                    print(f"   Compatibility: {info['compatibility']}")
                    
                    if info['latest_version']:
                        latest = info['latest_version']
                        print(f"   Latest: v{latest.get('version')} (ID: {latest.get('id')})")
                        
                        # Parse and display schema name/type
                        try:
                            schema_obj = json.loads(latest.get('schema', '{}'))
                            schema_name = schema_obj.get('name', schema_obj.get('type', 'Unknown'))
                            print(f"   Schema: {schema_name}")
                        except:
                            print(f"   Schema: [parsing error]")
                            
                except Exception as e:
                    print(f"   ❌ Error getting details: {e}")
        
        return True
    
    def export_schemas(self, output_dir: Path) -> bool:
        """Export all registered schemas to files"""
        print(f"\n💾 Exporting schemas to {output_dir}...")
        
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            subjects = self.list_subjects()
            
            for subject in subjects:
                info = self.get_detailed_subject_info(subject)
                if info['latest_version']:
                    schema_content = info['latest_version'].get('schema')
                    if schema_content:
                        output_file = output_dir / f"{subject}.avsc"
                        with open(output_file, 'w') as f:
                            # Pretty print the schema JSON
                            schema_obj = json.loads(schema_content)
                            json.dump(schema_obj, f, indent=2)
                        print(f"✅ Exported {subject} to {output_file}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error exporting schemas: {e}")
            return False
    
def print_usage():
    """Print usage information"""
    print("""
� Redpanda Schema Registry Management Tool
Comprehensive management for Redpanda Schema Registry with full API support

USAGE:
    python init_schemas.py [COMMAND] [OPTIONS]

COMMANDS:
    init        Initialize and register all A2A schemas (default)
    verify      Verify A2A schema registration and compatibility
    list        List all registered subjects with versions
    info        Show detailed information about subjects
    export      Export schemas to files for backup/migration
    cleanup     Delete subjects (soft/hard delete with confirmation)
    health      Check Schema Registry health and configuration
    config      Show/set global compatibility configuration

OPTIONS:
    --registry-url URL    Schema Registry URL (default: http://localhost:18081)
    --no-compatibility    Skip compatibility checks during registration
    --no-policies         Skip setting up A2A-specific compatibility policies
    --permanent           Permanent deletion (for cleanup command)
    --output-dir DIR      Output directory (for export command)
    --subject SUBJECT     Target specific subject (for info/cleanup commands)
    --level LEVEL         Compatibility level (BACKWARD, FORWARD, FULL, etc.)
    --timeout SECONDS     Request timeout in seconds (default: 30)
    --help               Show this help message

COMPATIBILITY LEVELS:
    BACKWARD             New schema can read old data (default)
    BACKWARD_TRANSITIVE  New schema can read all previous data
    FORWARD              Old schema can read new data
    FORWARD_TRANSITIVE   All previous schemas can read new data
    FULL                 Bidirectional compatibility (new ↔ previous)
    FULL_TRANSITIVE      Bidirectional compatibility (all versions)
    NONE                 No compatibility checks

A2A-SPECIFIC FEATURES:
    - Automatic setup of optimized compatibility policies
    - Schema validation for task-requests, task-responses, negotiations
    - Health monitoring with detailed diagnostics
    - Export/import capabilities for schema migration
    - Safe deletion with confirmation prompts

EXAMPLES:
    # Initialize A2A schemas with policies
    python init_schemas.py init

    # Verify without compatibility setup
    python init_schemas.py init --no-policies

    # Check health and configuration
    python init_schemas.py health

    # List all subjects with version counts
    python init_schemas.py list

    # Get detailed info for specific subject
    python init_schemas.py info --subject task-requests-value

    # Export all schemas for backup
    python init_schemas.py export --output-dir ./backup-schemas

    # Set global compatibility level
    python init_schemas.py config --level FULL

    # Soft delete a subject (can be restored)
    python init_schemas.py cleanup --subject test-subject

    # Hard delete permanently (DANGEROUS!)
    python init_schemas.py cleanup --subject test-subject --permanent

REGISTRY API COVERAGE:
    ✅ Schema registration and retrieval
    ✅ Compatibility configuration (global/subject)
    ✅ Version management and evolution
    ✅ Schema deletion (soft/hard)
    ✅ Mode configuration (READONLY/READWRITE)
    ✅ Schema references and dependencies
    ✅ Health monitoring and diagnostics
    ✅ Supported format querying

For more information: https://docs.redpanda.com/docs/manage/schema-registry/
""")

def main():
    """Enhanced main function with full CLI support"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Redpanda Schema Registry Management Tool",
        add_help=False
    )
    
    parser.add_argument('command', nargs='?', default='init',
                       choices=['init', 'verify', 'list', 'info', 'export', 'cleanup', 'health', 'config'],
                       help='Command to execute')
    
    parser.add_argument('--registry-url', default=os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:18081"),
                       help='Schema Registry URL')
    
    parser.add_argument('--no-compatibility', action='store_true',
                       help='Skip compatibility checks during registration')
    
    parser.add_argument('--no-policies', action='store_true',
                       help='Skip setting up compatibility policies')
    
    parser.add_argument('--permanent', action='store_true',
                       help='Permanent deletion (for cleanup)')
    
    parser.add_argument('--output-dir', type=Path, default='./exported-schemas',
                       help='Output directory for exports')
    
    parser.add_argument('--subject', 
                       help='Target specific subject')
    
    parser.add_argument('--level', 
                       choices=[level.value for level in CompatibilityLevel],
                       help='Compatibility level')
    
    parser.add_argument('--timeout', type=int, default=30,
                       help='Request timeout in seconds')
    
    parser.add_argument('--help', action='store_true',
                       help='Show help message')
    
    args = parser.parse_args()
    
    if args.help:
        print_usage()
        sys.exit(0)
    
    print("� Redpanda Schema Registry Management Tool")
    print("=" * 50)
    print(f"�🔗 Schema Registry URL: {args.registry_url}")
    print(f"⚡ Command: {args.command}")
    
    # Initialize manager
    manager = RegistryManager(args.registry_url, args.timeout)
    
    try:
        if args.command == 'init':
            print("\n🚀 Initializing A2A schemas...")
            success = manager.register_a2a_schemas(
                check_compatibility=not args.no_compatibility,
                setup_policies=not args.no_policies
            )
            if success and manager.verify_a2a_schemas():
                print("\n✨ A2A schema initialization completed successfully!")
                sys.exit(0)
            else:
                print("\n❌ A2A schema initialization failed")
                sys.exit(1)
        
        elif args.command == 'verify':
            print("\n🔍 Verifying A2A schemas...")
            if manager.verify_a2a_schemas():
                print("\n✅ All A2A schemas verified successfully!")
                sys.exit(0)
            else:
                print("\n❌ A2A schema verification failed")
                sys.exit(1)
        
        elif args.command == 'list':
            print("\n📋 Listing subjects...")
            subjects = manager.list_subjects()
            if subjects:
                print(f"\nFound {len(subjects)} subjects:")
                for subject in subjects:
                    versions = manager.get_subject_versions(subject)
                    print(f"  • {subject} ({len(versions)} versions)")
            else:
                print("No subjects found")
        
        elif args.command == 'info':
            if not args.subject:
                subjects = manager.list_subjects()
                print(f"\n📋 Information for all {len(subjects)} subjects:")
                for subject in subjects:
                    info = manager.get_detailed_subject_info(subject)
                    print(f"\n🔸 {subject}:")
                    print(f"   Versions: {len(info['versions'])}")
                    print(f"   Compatibility: {info['compatibility']}")
                    if info['latest_version']:
                        print(f"   Latest: v{info['latest_version'].get('version')} (ID: {info['latest_version'].get('id')})")
            else:
                print(f"\n📋 Information for subject: {args.subject}")
                info = manager.get_detailed_subject_info(args.subject)
                if info['versions']:
                    print(f"Versions: {info['versions']}")
                    print(f"Compatibility: {info['compatibility']}")
                    if info['latest_version']:
                        latest = info['latest_version']
                        print(f"Latest version: {latest.get('version')}")
                        print(f"Schema ID: {latest.get('id')}")
                        print(f"Schema content:")
                        try:
                            schema_obj = json.loads(latest.get('schema', '{}'))
                            print(json.dumps(schema_obj, indent=2))
                        except:
                            print("  [Schema parsing error]")
                else:
                    print(f"Subject '{args.subject}' not found")
        
        elif args.command == 'export':
            print(f"\n💾 Exporting schemas to {args.output_dir}...")
            if manager.export_schemas(args.output_dir):
                print("✅ Export completed successfully!")
            else:
                print("❌ Export failed")
                sys.exit(1)
        
        elif args.command == 'cleanup':
            if not args.subject:
                print("❌ --subject is required for cleanup command")
                sys.exit(1)
            
            print(f"\n🧹 Cleaning up subject: {args.subject}")
            if args.permanent:
                print("⚠️  WARNING: This will PERMANENTLY delete the subject!")
                response = input("Type 'yes' to confirm: ")
                if response.lower() != 'yes':
                    print("Cleanup cancelled")
                    sys.exit(0)
            
            if manager.delete_subject(args.subject, args.permanent):
                print("✅ Cleanup completed successfully!")
            else:
                print("❌ Cleanup failed")
                sys.exit(1)
        
        elif args.command == 'health':
            print("\n🔍 Checking Schema Registry health...")
            if manager.check_registry_health():
                manager.get_global_compatibility()
                manager.get_global_mode()
                supported_formats = manager.query_supported_formats()
                print(f"Supported formats: {supported_formats}")
                print("✅ Schema Registry is healthy!")
            else:
                print("❌ Schema Registry health check failed")
                sys.exit(1)
        
        elif args.command == 'config':
            if args.level:
                print(f"\n🔧 Setting global compatibility to {args.level}...")
                level = CompatibilityLevel(args.level)
                if manager.set_global_compatibility(level):
                    print("✅ Compatibility level updated!")
                else:
                    print("❌ Failed to update compatibility level")
                    sys.exit(1)
            else:
                print("\n📋 Current configuration:")
                manager.get_global_compatibility()
                manager.get_global_mode()
        
        else:
            print(f"❌ Unknown command: {args.command}")
            print_usage()
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  Operation interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
