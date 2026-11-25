"""HTTP endpoints for the live review. Added to the API only when LIVE_API is switched on. Every call must send a
client's API key in the X-API-Key header, and the key decides which client's uploads the call can see: one client's
key can never read, review or delete another client's upload (it is answered as "not found").

    POST   /submissions                                  {filename, text}  -> queue an upload
    GET    /submissions                                  recent uploads
    GET    /submissions/{id}                             status, progress and every answer
    PUT    /submissions/{id}/answers/{answer}/review     {reviewer, action: confirm|reject, note}
    DELETE /submissions/{id}/answers/{answer}/review     take a review back
    DELETE /submissions/{id}                             remove the upload and everything derived from it
"""
from cuad_ai.live import store, tenants
from cuad_ai.live.store import LimitReached, RejectedUpload


def add_live_routes(app, connect):
    from fastapi import Depends, Header, HTTPException
    from pydantic import BaseModel

    def current_tenant(x_api_key: str = Header(default="")):
        with connect() as conn:
            tenant = tenants.tenant_for_key(conn, x_api_key)
        if tenant is None:
            raise HTTPException(status_code=401, detail="a valid X-API-Key header is required")
        return tenant

    class Upload(BaseModel):
        filename: str
        text: str

    class Review(BaseModel):
        reviewer: str
        action: str
        note: str = ""

    @app.post("/submissions", status_code=202)
    def create_submission(upload: Upload, tenant: str = Depends(current_tenant)):
        with connect() as conn:
            try:
                sid = store.submit(conn, tenant, upload.filename, upload.text, uploaded_by=f"api:{tenant}")
            except LimitReached as error:
                raise HTTPException(status_code=429, detail=str(error)) from None
            except RejectedUpload as error:
                raise HTTPException(status_code=422, detail=str(error)) from None
            tenants.audit(conn, tenant, f"api:{tenant}", "upload", sid, upload.filename)
            return store.get_submission(conn, tenant, sid)

    @app.get("/submissions")
    def list_submissions(limit: int = 50, tenant: str = Depends(current_tenant)):
        with connect() as conn:
            return store.list_submissions(conn, tenant, max(1, min(limit, 200)))

    @app.get("/submissions/{submission_id}")
    def get_submission(submission_id: int, tenant: str = Depends(current_tenant)):
        with connect() as conn:
            submission = store.get_submission(conn, tenant, submission_id)
            if submission is None:
                raise HTTPException(status_code=404, detail="no such upload")
            tenants.audit(conn, tenant, f"api:{tenant}", "view", submission_id)
            return {**submission, "answers": store.get_answers(conn, tenant, submission_id)}

    @app.put("/submissions/{submission_id}/answers/{answer_id}/review")
    def review(submission_id: int, answer_id: int, body: Review, tenant: str = Depends(current_tenant)):
        with connect() as conn:
            try:
                store.review_answer(conn, tenant, submission_id, answer_id, body.reviewer, body.action, body.note)
            except LookupError:
                raise HTTPException(status_code=404, detail="no such answer") from None
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from None
            tenants.audit(conn, tenant, f"api:{tenant}", f"review:{body.action}", submission_id,
                          f"answer {answer_id} by {body.reviewer}")
        return {"status": "saved"}

    @app.delete("/submissions/{submission_id}/answers/{answer_id}/review")
    def clear_review(submission_id: int, answer_id: int, tenant: str = Depends(current_tenant)):
        with connect() as conn:
            if store.clear_review(conn, tenant, submission_id, answer_id):
                tenants.audit(conn, tenant, f"api:{tenant}", "review:clear", submission_id, f"answer {answer_id}")
        return {"status": "cleared"}

    @app.delete("/submissions/{submission_id}")
    def delete_submission(submission_id: int, tenant: str = Depends(current_tenant)):
        with connect() as conn:
            if not store.delete_submission(conn, tenant, submission_id):
                raise HTTPException(status_code=404, detail="no such upload")
            tenants.audit(conn, tenant, f"api:{tenant}", "delete", submission_id)
        return {"status": "deleted"}
