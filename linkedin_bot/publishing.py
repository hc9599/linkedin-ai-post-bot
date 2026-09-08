"""
Post the finished text to LinkedIn.

Needs LINKEDIN_TOKEN and LINKEDIN_PERSON_ID in the environment.
"""
from typing import Protocol

from linkedin_bot.config import linkedin_credentials
from linkedin_bot.http import request_write_with_retry


class Publisher(Protocol):
    """A place we can publish. LinkedIn is the only one right now."""
    def publish(self, content: str) -> None:
        ...


class LinkedInPublisher:
    """Talks to LinkedIn's API. Timeouts + retries so GitHub Actions does not hang forever."""
    def publish(self, content: str) -> None:
        token, person_id = linkedin_credentials()
        url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        payload = {
            "author": f"urn:li:person:{person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

        response = request_write_with_retry("POST", url, headers=headers, json=payload)

        if response.status_code not in [200, 201]:
            raise Exception(f"LinkedIn API error: {response.status_code} - {response.text}")

        print("Successfully posted to LinkedIn!")
        return response.json()
