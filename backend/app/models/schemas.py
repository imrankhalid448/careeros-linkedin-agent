from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    full_name: str = ""
    headline: str = ""
    about: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    portfolio_links: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    work_preferences: str = ""
    work_authorization: str = ""
    linkedin_raw_text: str = ""
    voice_notes: str = ""
    confirmed: bool = False


class ProjectNoteCreate(BaseModel):
    title: str
    content: str
    github_url: str = ""
    tags: list[str] = Field(default_factory=list)


class PostGenerateRequest(BaseModel):
    platform: str = "linkedin"
    source_type: str = "idea"  # project_note | github | idea
    project_note_id: int | None = None
    github_url: str = ""
    idea: str = ""
    tone_hint: str = ""


class PostUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    scheduled_for: str | None = None


class CommentGenerateRequest(BaseModel):
    platform: str = "linkedin"
    target_url: str = ""
    source_post_text: str = ""
    intent: str = ""


class CommentUpdateRequest(BaseModel):
    draft_reply: str


class LinkedInImportRequest(BaseModel):
    profile_text: str = ""


class JobImportRequest(BaseModel):
    raw_text: str = ""
    apply_url: str = ""
    source_type: str = "pasted"  # pasted | email | url


class TrackJobRequest(BaseModel):
    title: str
    company: str = ""
    location: str = ""
    work_mode: str = "unknown"
    apply_url: str = ""
    description: str = ""
    source: str = "discovered"


class JobStatusUpdate(BaseModel):
    status: str  # Saved | Preparing | Applied | Interview | Offer | Rejected


class AutopilotUpdate(BaseModel):
    enabled: bool | None = None
    auto_publish: bool | None = None
    posts_per_day: int | None = Field(default=None, ge=3, le=5)
    timezone: str | None = None
    slots: list[str] | None = None


class ChatRequest(BaseModel):
    message: str


class AISettingsUpdate(BaseModel):
    ai_provider: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    external_ai_base_url: str | None = None
    external_ai_model: str | None = None
    external_ai_api_key: str | None = None
    hf_token: str | None = None
