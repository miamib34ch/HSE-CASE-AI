from enum import StrEnum


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    REQUIREMENTS_UPLOADED = "requirements_uploaded"
    REQUIREMENTS_STRUCTURED = "requirements_structured"
    REQUIREMENTS_CONFIRMED = "requirements_confirmed"
    CODE_GENERATED = "code_generated"
    TESTS_GENERATED = "tests_generated"
    DEPLOYED = "deployed"
    FAILED = "failed"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    APPROVAL_REQUIRED = "approval_required"


class TaskType(StrEnum):
    REQUIREMENTS_ANALYSIS = "requirements_analysis"
    CODE_GENERATION = "code_generation"
    SCHEMA_GENERATION = "schema_generation"
    TEST_GENERATION = "test_generation"
    DEPLOYMENT = "deployment"
    AGENT_EXECUTION = "agent_execution"


class ArtifactType(StrEnum):
    RAW_REQUIREMENTS = "raw_requirements"
    STRUCTURED_REQUIREMENTS_JSON = "structured_requirements_json"
    STRUCTURED_REQUIREMENTS_MARKDOWN = "structured_requirements_markdown"
    GENERATED_CODE = "generated_code"
    GENERATED_DIAGRAM = "generated_diagram"
    GENERATED_TESTS = "generated_tests"
    GENERATED_DOCS = "generated_docs"
    DEPLOYMENT_BUNDLE = "deployment_bundle"
    MANUAL_UPLOAD = "manual_upload"


class TransportType(StrEnum):
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"
    HTTP_SSE = "http_sse"


class TrustLevel(StrEnum):
    LOCAL_TRUSTED = "local_trusted"
    REMOTE_VERIFIED = "remote_verified"
    REMOTE_UNTRUSTED = "remote_untrusted"


class ApprovalMode(StrEnum):
    ALWAYS = "always"
    SIDE_EFFECT_ONLY = "side_effect_only"
    NEVER = "never"
