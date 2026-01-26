#!/usr/bin/env python3
"""
Microsoft Forms MCP Server

Fetches form structure, aggregated data, and individual responses from Microsoft Forms.
Since this uses the private Forms API (not Graph API), authentication requires a
verification token captured from an authenticated browser session.

Environment Variables:
    MS_FORMS_TOKEN: The __requestverificationtoken from an authenticated Forms session

Usage:
    1. Open Microsoft Forms in browser, open DevTools Network tab
    2. Capture any API request and copy the __requestverificationtoken header
    3. Set MS_FORMS_TOKEN environment variable
    4. Call get_form_data() with the form ID (owner is auto-detected from the ID)
"""

import base64
import json
import os
import re
import urllib.request
import urllib.error
from typing import Annotated, Any, Optional
from urllib.parse import urlparse, parse_qs

from mcp.server.fastmcp import FastMCP
from pydantic import Field
import logging

# Import schemas for validation (optional)
try:
    from schemas import FormQuestion, FormSummaryQuestion, FormResponse, FormSummaryResult, FormDataResult
    HAS_SCHEMAS = True
except ImportError:
    try:
        from .schemas import FormQuestion, FormSummaryQuestion, FormResponse, FormSummaryResult, FormDataResult
        HAS_SCHEMAS = True
    except ImportError:
        HAS_SCHEMAS = False


# Tool descriptions - just description + Returns line
# The agent reads full Input/Output from generated docs (.mcp/docs/msforms.md)

_FORM_DATA_DOC = "Fetch complete form data with structure, summary stats, and individual responses."

_FORM_SUMMARY_DOC = "Fetch aggregated summary statistics for a form (faster, no individual responses)."

# Configure logging (writes to stderr, won't interfere with MCP protocol)
logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
logger = logging.getLogger("msforms")

# Initialize MCP server
mcp = FastMCP("msforms")

# API base
FORMS_API_BASE = "https://forms.office.com/formapi/api"

# Tenant ID - set via MS_FORMS_TENANT env var in mcp-servers.json
MS_TENANT_ID = os.environ.get("MS_FORMS_TENANT", "YOUR_MS_TENANT_ID")

# Full query parameters for light/forms endpoint (ensures all fields including question titles are returned)
LIGHT_FORMS_QUERY = (
    "?$select=DataClassificationLabel,background,category,collectionId,createdBy,createdDate,"
    "defaultLanguage,description,descriptiveQuestions,distributionInfo,emailReceiptConsent,"
    "emailReceiptEnabled,fillOutRemainingTime,fillOutTimeLimit,flags,footerText,formsInsightsInfo,"
    "formsProRTDescription,formsProRTTitle,id,lastSyncedResponseId,localeInfo,localeList,"
    "localeResources,localizedResources,logo,migrationWorkbookId,modernSettings,modifiedDate,"
    "onlineSafetyLevel,order,otherInfo,ownerId,ownerTenantId,permissionTokens,permissions,"
    "privacyUrl,progressBarEnabled,questions,reputationTier,responderPermissions,responses,"
    "rowCount,settings,smartConvertMetaData,softDeleted,startedDate,status,subTitle,"
    "teamsPollProperty,tenantSwitches,termsUrl,thankYouMessage,themeV2,title,trackingId,type,"
    "version,xlExportingTag,xlFileUnSynced,xlUnsyncedReason,xlTableId,xlWorkbookId,sdxWebUrl,"
    "sdxWorkbookId,sdxWorkbookParentDriveId,sdxWorkbookParentFolder,sdxWorkbookParentFolderId,"
    "sdxWorkbookFileName,sdxWorkbookOwner,sensitivityLabel,userIntention,insightsOutlines"
    "&$expand=permissions,permissionTokens,questions($expand=choices)"
)

# Form ID encoding constants
ORG_ID_SIZE = 16  # bytes
OWNER_ID_SIZE = 16  # bytes
PADDING = "."
SEPARATOR = "$%@#"


# =============================================================================
# Form ID Decoder (ported from TypeScript FormIdUtility.ts)
# =============================================================================

def _bytes_to_guid_string(b: bytes) -> str:
    """Convert 16 bytes to a GUID string with proper byte order."""
    if len(b) != 16:
        raise ValueError("GUID must be 16 bytes")
    
    # Reverse byte order for first 3 sections (little-endian to big-endian)
    reordered = (
        bytes(reversed(b[0:4])) +   # Data1: 4 bytes reversed
        bytes(reversed(b[4:6])) +   # Data2: 2 bytes reversed
        bytes(reversed(b[6:8])) +   # Data3: 2 bytes reversed
        b[8:16]                      # Data4: 8 bytes as-is
    )
    
    hex_str = reordered.hex()
    return f"{hex_str[0:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:32]}"


def decode_form_id(form_id: str) -> dict[str, Optional[str]]:
    """
    Decode a Microsoft Forms ID to extract OrgId, OwnerId, and TableId.
    
    The form ID is base64 encoded with the structure:
    [16 bytes: OrgId GUID][16 bytes: OwnerId GUID][remaining: TableId + metadata]
    
    Args:
        form_id: The encoded form ID string
        
    Returns:
        Dict with keys: OrgId, OwnerId, TableId, IsGroupOwner, ContainerId
    """
    try:
        # Replace URL-safe base64 chars back to standard
        form_id_clean = form_id.replace("_", "/").replace("-", "+")
        
        # Decode from base64
        form_id_bytes = base64.b64decode(form_id_clean)
        
        # Extract OrgId (first 16 bytes)
        org_id_bytes = form_id_bytes[:ORG_ID_SIZE]
        org_id = _bytes_to_guid_string(org_id_bytes)
        
        # Extract OwnerId (next 16 bytes)
        owner_id_bytes = form_id_bytes[ORG_ID_SIZE:ORG_ID_SIZE + OWNER_ID_SIZE]
        owner_id = _bytes_to_guid_string(owner_id_bytes)
        
        # Extract TableId (remaining bytes)
        table_id_bytes = form_id_bytes[ORG_ID_SIZE + OWNER_ID_SIZE:]
        table_id = table_id_bytes.decode("ascii", errors="replace").rstrip(PADDING)
        
        # Parse metadata after separator
        is_group_owner = False
        container_id = "0"
        
        if SEPARATOR in table_id:
            parts = table_id.split(SEPARATOR)
            table_id = parts[0]
            for part in parts[1:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    if key == "t" and value == "g":
                        is_group_owner = True
                    elif key == "c":
                        container_id = value
        
        return {
            "OrgId": org_id,
            "OwnerId": owner_id,
            "TableId": table_id,
            "IsGroupOwner": is_group_owner,
            "ContainerId": container_id,
        }
    except Exception as e:
        return {
            "OrgId": None,
            "OwnerId": None,
            "TableId": None,
            "IsGroupOwner": None,
            "ContainerId": None,
            "error": str(e),
        }


# =============================================================================
# HTTP Helpers
# =============================================================================

def _get_headers(token: str) -> dict[str, str]:
    """Build request headers with auth token, bearer auth, and cookies."""
    headers = {
        "__requestverificationtoken": token,
        "accept": "application/json",
        "content-type": "application/json",
        "odata-version": "4.0",
        "x-ms-form-request-ring": "fastfood",
        "x-ms-form-request-source": "ms-formweb",
    }
    
    # Add Bearer token if provided (required for API calls)
    bearer = os.environ.get("MS_FORMS_BEARER", "")
    if bearer:
        headers["authorization"] = f"Bearer {bearer}"
    
    # Add cookies if provided
    cookies = os.environ.get("MS_FORMS_COOKIES", "")
    if cookies:
        headers["cookie"] = cookies
    
    return headers


def _parse_form_url(form_url: str) -> tuple[str, str, str]:
    """
    Parse a Microsoft Forms URL to extract tenant_id, user_id, and form_id.
    
    Supports formats:
    - https://forms.office.com/Pages/ResponsePage.aspx?id=FORM_ID
    - https://forms.office.com/r/FORM_ID
    - https://forms.office.com/Pages/DesignPageV2.aspx?...&id=FORM_ID
    
    Returns: (tenant_id, user_id, form_id) - note: tenant/user may need to be 
             fetched from the form metadata for short URLs
    """
    parsed = urlparse(form_url)
    
    # Extract form_id from query params
    query = parse_qs(parsed.query)
    form_id = query.get("id", [None])[0]
    
    # Handle short URLs like /r/FORM_ID
    if not form_id and "/r/" in form_url:
        match = re.search(r"/r/([A-Za-z0-9_-]+)", form_url)
        if match:
            form_id = match.group(1)
    
    if not form_id:
        raise ValueError(f"Could not extract form ID from URL: {form_url}")
    
    # For the private API, we need tenant_id and user_id
    # These are typically embedded in the form_id or obtained from form metadata
    # The form_id format is usually: v4j5cvGGr0GRqy180BHbR...
    
    # Tenant and user from environment (set in mcp-servers.json)
    tenant_id = os.environ.get("MS_FORMS_TENANT", "YOUR_MS_TENANT_ID")
    user_id = os.environ.get("MS_FORMS_USER", "YOUR_MS_FORMS_USER_ID")
    
    return tenant_id, user_id, form_id


def _extract_form_id(form_id_or_url: str) -> str:
    """
    Extract form ID from either a URL or a raw form ID.
    
    Accepts:
        - Raw form ID: 'v4j5cvGGr0GRqy180BHbR...'
        - Full URL: 'https://forms.office.com/r/v4j5cvGGr0GRqy180BHbR...'
        - Response URL: 'https://forms.office.com/Pages/ResponsePage.aspx?id=...'
    
    Returns: The raw form ID string
    """
    s = form_id_or_url.strip()
    
    # If it looks like a URL, extract the form ID
    if s.startswith("http://") or s.startswith("https://"):
        _, _, form_id = _parse_form_url(s)
        return form_id
    
    # Otherwise assume it's already a raw form ID
    return s


# System fields returned by aggregate API that are NOT user questions
SYSTEM_FIELDS = frozenset({
    "ResponderName", "UserId", "Responder", "ResponseLastUpdatedTime",
    "StartDate", "SubmitDate", "ID"
})


def _normalize_question_type(raw_type: str) -> str:
    """
    Normalize question type to simple names: 'choice', 'rating', 'text'.
    
    Raw API returns:
      - Questions: 'Question.Choice', 'Question.Rating', 'Question.TextField'
      - Summary: 'formChoiceData', 'ratingData', 'textData'
    """
    t = raw_type.lower()
    if "choice" in t:
        return "choice"
    elif "rating" in t:
        return "rating"
    elif "text" in t or "textfield" in t:
        return "text"
    elif "date" in t:
        return "date"
    elif "number" in t:
        return "number"
    elif "ranking" in t:
        return "ranking"
    elif "nps" in t:
        return "nps"
    else:
        return raw_type  # fallback to original


def _fetch_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    """Make a GET request and return JSON response."""
    logger.info(f"Fetching: {url}")
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error(f"HTTP {e.code} from {url}: {body[:200]}")
        raise RuntimeError(f"HTTP {e.code}: {body[:500]}")


def _parse_answers(answers_json: str) -> list[dict[str, Any]]:
    """Parse the double-encoded answers JSON string."""
    if not answers_json:
        return []
    
    try:
        answers = json.loads(answers_json)
    except json.JSONDecodeError:
        return []
    
    parsed = []
    for ans in answers:
        question_id = ans.get("questionId", "")
        answer1 = ans.get("answer1", "")
        
        # Try to parse multi-select answers (they're JSON arrays as strings)
        if isinstance(answer1, str) and answer1.startswith("["):
            try:
                answer1 = json.loads(answer1)
            except json.JSONDecodeError:
                pass
        
        parsed.append({
            "questionId": question_id,
            "answer": answer1,
        })
    
    return parsed


def _parse_question_info(question_info_json: str) -> dict[str, Any]:
    """Parse the questionInfo JSON string to extract choices, ratings, etc."""
    if not question_info_json:
        return {}
    
    try:
        return json.loads(question_info_json)
    except json.JSONDecodeError:
        return {}


@mcp.tool(description=_FORM_DATA_DOC)
def get_form_data(
    form: Annotated[str, Field(description="Form URL (e.g. 'https://forms.office.com/r/abc123')")],
    max_responses: Annotated[int | None, Field(description="Maximum responses to fetch (default: all)")] = None,
) -> dict[str, Any]:
    """Fetch form data with questions, summary stats, and individual responses."""
    # Extract form ID from URL if needed
    form_id = _extract_form_id(form)
    logger.info(f"get_form_data called: form_id={form_id[:20]}..., max_responses={max_responses}")
    
    # Get auth token from environment
    token = os.environ.get("MS_FORMS_TOKEN", "")
    if not token:
        raise RuntimeError(
            "MS_FORMS_TOKEN environment variable not set. "
            "Capture the __requestverificationtoken from an authenticated Forms session."
        )
    
    # Decode form ID to get owner
    decoded = decode_form_id(form_id)
    if not decoded.get("OwnerId"):
        raise RuntimeError(
            f"Could not decode form ID to extract owner. "
            f"Decode error: {decoded.get('error', 'unknown')}"
        )
    
    tenant_id = MS_TENANT_ID
    user_id = decoded["OwnerId"]
    logger.info(f"Decoded owner: {user_id}")
    
    headers = _get_headers(token)
    
    # 1. Fetch form metadata (structure + questions)
    metadata_url = f"{FORMS_API_BASE}/{tenant_id}/users/{user_id}/light/forms('{form_id}'){LIGHT_FORMS_QUERY}"
    metadata = _fetch_json(metadata_url, headers)
    
    # Parse questions into a dict keyed by question ID for consistent joins
    raw_questions = metadata.get("questions", [])
    questions = {}  # id -> question object (dict for O(1) lookup)
    
    for q in raw_questions:
        q_id = q.get("id", "")
        q_info = _parse_question_info(q.get("questionInfo", ""))
        
        parsed_q = {
            "id": q_id,
            "title": q.get("title", ""),
            "type": _normalize_question_type(q.get("type", "")),
            "required": q.get("required", False),
        }
        
        # Extract choices for choice questions
        # Note: questionInfo JSON has Choices with "Description" key
        if "Choices" in q_info:
            parsed_q["choices"] = [
                c.get("Description", c.get("FormsProDisplayRTText", "")) 
                for c in q_info.get("Choices", [])
            ]
        
        # Extract rating info (e.g., Length=5, MinRating=1 → 1-5 scale)
        if "Length" in q_info:
            parsed_q["ratingScale"] = q_info.get("Length", 5)
        elif "RatingCount" in q_info:
            parsed_q["ratingScale"] = q_info.get("RatingCount", 5)
        
        questions[q_id] = parsed_q
    
    # 2. Fetch aggregated summary
    summary_url = (
        f"{FORMS_API_BASE}/{tenant_id}/users/{user_id}/"
        f"forms('{form_id}')/GetAggregateSurveyData"
    )
    summary_raw = _fetch_json(summary_url, headers)
    
    # Parse summary into a more usable format
    # Filter out system fields - only include actual question IDs
    summary = {}
    avg_submit_time = None
    
    for item in summary_raw.get("value", []):
        col_name = item.get("columnPropertyName")
        if not col_name:
            # This is the overall summary - extract for form metadata
            avg_submit_time = item.get("summaryData", {}).get("averageSubmitTimeSeconds")
            continue
        
        # Skip system fields - only include actual question IDs
        if col_name in SYSTEM_FIELDS:
            continue
        
        agg_type = item.get("aggregationDataType", "")
        entry = {"questionId": col_name, "type": _normalize_question_type(agg_type)}
        
        if agg_type == "ratingData":
            rating = item.get("ratingData", {})
            entry["average"] = rating.get("average")
            entry["count"] = rating.get("count", 0)
            entry["distribution"] = {
                r["id"]: r["count"] 
                for r in rating.get("ratingCount", [])
            }
        elif agg_type == "formChoiceData":
            entry["distribution"] = {
                c["id"]: c["count"] 
                for c in item.get("formChoiceData", [])
            }
        elif agg_type == "textData":
            text_data = item.get("textData", {})
            entry["count"] = text_data.get("count", 0)
            entry["recentValues"] = [
                v for v in text_data.get("recentValues", []) if v
            ]
        
        summary[col_name] = entry
    
    # 3. Fetch individual responses (paginated)
    # Use rowCount from metadata to determine total responses, default to fetching all
    total_responses = metadata.get("rowCount", 0)
    fetch_limit = max_responses if max_responses is not None else total_responses
    logger.info(f"Total responses in form: {total_responses}, fetching up to: {fetch_limit}")
    
    responses = []
    page_size = 50
    skip = 0
    
    while len(responses) < fetch_limit:
        responses_url = (
            f"{FORMS_API_BASE}/{tenant_id}/users/{user_id}/light/"
            f"forms('{form_id}')/responses?$expand=comments&$top={page_size}&$skip={skip}"
        )
        
        try:
            page = _fetch_json(responses_url, headers)
        except Exception:
            break  # Stop on error (e.g., end of data)
        
        page_responses = page.get("value", [])
        if not page_responses:
            break
        
        for resp in page_responses:
            if len(responses) >= fetch_limit:
                break
            
            parsed_answers = _parse_answers(resp.get("answers", ""))
            
            # Build response record with answers keyed by question ID
            # This allows consistent joins: questions[q_id], summary[q_id], response["answers"][q_id]
            response_record = {
                "id": resp.get("id"),
                "submitDate": resp.get("submitDate"),
                "responder": resp.get("responder"),
                "answers": {},
            }
            
            # Key answers by question ID for consistent joins
            # Convert rating answers to integers for easier comparison
            for ans in parsed_answers:
                q_id = ans["questionId"]
                value = ans["answer"]
                
                # Convert rating answers (strings like "4") to integers
                q_info = questions.get(q_id, {})
                if q_info.get("type") == "rating" and isinstance(value, str):
                    try:
                        value = int(value)
                    except ValueError:
                        pass  # Keep as string if conversion fails
                
                response_record["answers"][q_id] = value
            
            responses.append(response_record)
        
        skip += page_size
        
        if len(page_responses) < page_size:
            break
    
    # Return structured result
    # - questions: dict keyed by question ID
    # - summary: dict keyed by question ID  
    # - responses: list with answers keyed by question ID
    # This allows: questions[q_id], summary[q_id], response["answers"][q_id]
    return {
        "title": metadata.get("title", ""),
        "description": metadata.get("description", ""),
        "responseCount": metadata.get("rowCount", len(responses)),
        "questions": questions,
        "summary": summary,
        "responses": responses,
    }


@mcp.tool(description=_FORM_SUMMARY_DOC)
def get_form_summary(
    form: Annotated[str, Field(description="Form URL (e.g. 'https://forms.office.com/r/abc123')")],
) -> dict[str, Any]:
    """Fetch aggregated summary statistics for a form (faster than get_form_data)."""
    # Extract form ID from URL if needed
    form_id = _extract_form_id(form)
    logger.info(f"get_form_summary called: form_id={form_id[:20]}...")
    
    token = os.environ.get("MS_FORMS_TOKEN", "")
    if not token:
        raise RuntimeError("MS_FORMS_TOKEN environment variable not set.")
    
    # Decode form ID to get owner
    decoded = decode_form_id(form_id)
    if not decoded.get("OwnerId"):
        raise RuntimeError(f"Could not decode form ID: {decoded.get('error', 'unknown')}")
    
    tenant_id = MS_TENANT_ID
    user_id = decoded["OwnerId"]
    logger.info(f"Decoded owner: {user_id}")
    
    headers = _get_headers(token)
    
    # Fetch metadata (includes questions with titles)
    metadata_url = f"{FORMS_API_BASE}/{tenant_id}/users/{user_id}/light/forms('{form_id}'){LIGHT_FORMS_QUERY}"
    metadata = _fetch_json(metadata_url, headers)
    
    question_titles = {
        q.get("id", ""): q.get("title", "") 
        for q in metadata.get("questions", [])
    }
    
    # Fetch aggregated data
    summary_url = (
        f"{FORMS_API_BASE}/{tenant_id}/users/{user_id}/"
        f"forms('{form_id}')/GetAggregateSurveyData"
    )
    summary_raw = _fetch_json(summary_url, headers)
    
    result = {
        "title": metadata.get("title", ""),
        "responseCount": metadata.get("rowCount", 0),
        "avgSubmitTimeSeconds": None,
        "questions": {},  # Keyed by question ID for consistency with get_form_data
    }
    
    for item in summary_raw.get("value", []):
        q_id = item.get("columnPropertyName")
        if not q_id:
            result["avgSubmitTimeSeconds"] = (
                item.get("summaryData", {}).get("averageSubmitTimeSeconds")
            )
            continue
        
        # Skip system fields - only include actual question IDs
        if q_id in SYSTEM_FIELDS:
            continue
        
        q_title = question_titles.get(q_id, q_id)
        agg_type = item.get("aggregationDataType", "")
        
        # Key by question ID, include title for display
        if agg_type == "ratingData":
            rating = item.get("ratingData", {})
            result["questions"][q_id] = {
                "id": q_id,
                "title": q_title,
                "type": "rating",
                "average": rating.get("average"),
                "distribution": {r["id"]: r["count"] for r in rating.get("ratingCount", [])},
            }
        elif agg_type == "formChoiceData":
            result["questions"][q_id] = {
                "id": q_id,
                "title": q_title,
                "type": "choice",
                "distribution": {c["id"]: c["count"] for c in item.get("formChoiceData", [])},
            }
        elif agg_type == "textData":
            text_data = item.get("textData", {})
            result["questions"][q_id] = {
                "id": q_id,
                "title": q_title,
                "type": "text",
                "count": text_data.get("count", 0),
                "samples": [v for v in text_data.get("recentValues", [])[:3] if v],
            }
    
    return result


if __name__ == "__main__":
    mcp.run()
