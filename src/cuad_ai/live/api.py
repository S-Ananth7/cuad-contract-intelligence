"""HTTP endpoints for the live review. Added to the API only when LIVE_API_KEY is set; every call must send it
in the X-API-Key header.

    POST   /submissions                                  {filename, text}  -> queue an upload
    GET    /submissions                                  recent uploads
    GET    /submissions/{id}                             status, progress and every answer
    PUT    /submissions/{id}/answers/{answer}/review     {reviewer, action: confirm|reject, note}
    DELETE /submissions/{id}/answers/{answer}/review     take a review back
    DELETE /submissions/{id}                             remove the upload and everything derived from it
"""
import hmac

from cuad_ai.live import config, store
from cuad_ai.live.store import LimitReached, RejectedUpload


def add_live_routes(app, connect):
    from fastapi import Depends, Header, HTTPException
    from pydantic import BaseModel

    def require_key(x_api_key: str = Header(default="")):
        key = config.access_key()
        if not key or not hmac.compare_digest(x_api_key.encode(), key.encode()):
            raise HTTPException(status_code=401, detail="a valid X-API-Key header is required")

    class Upload(BaseModel):
        filename: str
        text: str

    class Review(BaseModel):
        reviewer: str
        action: str
        note: str = ""

    guard = [Depends(require_key)]

    @app.post("/submissions", status_code=202, dependencies=guard)
    def create_submission(upload: Upload):
        with connect() as conn:
            try:
                sid = store.submit(conn, upload.filename, upload.text)
            except LimitReached as error:
                raise HTTPException(status_code=429, detail=str(error)) from None
            except RejectedUpload as error:
                raise HTTPException(status_code=422, detail=str(error)) from None
            return store.get_submission(conn, sid)

    @app.get("/submissions", dependencies=guard)
    def list_submissions(limit: int = 50):
        with connect() as conn:
            return store.list_submissions(conn, max(1, min(limit, 200)))

    @app.get("/submissions/{submission_id}", dependencies=guard)
    def get_submission(submission_id: int):
        with connect() as conn:
            submission = store.get_submission(conn, submission_id)
            if submission is None:
                raise HTTPException(status_code=404, detail="no such upload")
            return {**submission, "answers": store.get_answers(conn, submission_id)}

    @app.put("/submissions/{submission_id}/answers/{answer_id}/review", dependencies=guard)
    def review(submission_id: int, answer_id: int, body: Review):
        with connect() as conn:
            try:
                store.review_answer(conn, submission_id, answer_id, body.reviewer, body.action, body.note)
            except LookupError:
                raise HTTPException(status_code=404, detail="no such answer") from None
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from None
        return {"status": "saved"}

    @app.delete("/submissions/{submission_id}/answers/{answer_id}/review", dependencies=guard)
    def clear_review(submission_id: int, answer_id: int):
        with connect() as conn:
            store.clear_review(conn, submission_id, answer_id)
        return {"status": "cleared"}

    @app.delete("/submissions/{submission_id}", dependencies=guard)
    def delete_submission(submission_id: int):
        with connect() as conn:
            if not store.delete_submission(conn, submission_id):
                raise HTTPException(status_code=404, detail="no such upload")
        return {"status": "deleted"}
