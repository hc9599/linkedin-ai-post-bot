"""
Post the finished text (and maybe a picture) to LinkedIn.

Needs LINKEDIN_TOKEN and LINKEDIN_PERSON_ID in the environment.
If the picture upload fails, we still post the text so the day is not wasted.
"""
from typing import Protocol

from linkedin_bot.config import linkedin_credentials
from linkedin_bot.http import request_write_with_retry


class Publisher(Protocol):
    """A place we can publish. LinkedIn is the only one right now."""
    def publish(self, content: str, image_bytes: bytes | None = None):
        ...


class LinkedInPublisher:
    """Talks to LinkedIn's API. Timeouts + retries so GitHub Actions does not hang forever."""
    def publish(self, content: str, image_bytes: bytes | None = None):
        token, person_id = linkedin_credentials()
        url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        if image_bytes:
            try:
                asset = self._upload_image(image_bytes, token, person_id)
                payload = {
                    "author": f"urn:li:person:{person_id}",
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": content},
                            "shareMediaCategory": "IMAGE",
                            "media": [
                                {
                                    "status": "READY",
                                    "media": asset,
                                }
                            ],
                        }
                    },
                    "visibility": {
                        "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                    },
                }
                print("Posting with image...")
            except Exception as e:
                print(f"Image upload failed ({e}) — falling back to text-only post")
                image_bytes = None

        if not image_bytes:
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

    def _upload_image(self, image_bytes: bytes, token: str, person_id: str) -> str:
        """
        Uploads image bytes to LinkedIn using the Assets API.
        Returns the asset URN needed to attach the image to a post.
        """
        headers_base = {
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": f"urn:li:person:{person_id}",
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        }

        reg_response = request_write_with_retry(
            "POST",
            register_url,
            headers={**headers_base, "Content-Type": "application/json"},
            json=register_payload,
        )

        if reg_response.status_code != 200:
            raise Exception(
                f"LinkedIn image register failed: {reg_response.status_code} - {reg_response.text}"
            )

        reg_data = reg_response.json()
        upload_url = (
            reg_data["value"]["uploadMechanism"]
            ["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]
            ["uploadUrl"]
        )
        asset = reg_data["value"]["asset"]

        print(f"LinkedIn upload URL obtained. Asset: {asset}")

        upload_response = request_write_with_retry(
            "PUT",
            upload_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "image/png",
            },
            data=image_bytes,
        )

        if upload_response.status_code not in [200, 201]:
            raise Exception(
                f"LinkedIn image upload failed: {upload_response.status_code} - {upload_response.text}"
            )

        print("Image uploaded to LinkedIn successfully.")
        return asset
