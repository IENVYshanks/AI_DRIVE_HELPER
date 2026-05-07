import requests
import streamlit as st

from src.config_env import get_env, load_env_file

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
IMAGE_MIME_PREFIX = "image/"

load_env_file()

BACKEND_URL = get_env("BACKEND_URL", "http://127.0.0.1:8000")


@st.cache_data(show_spinner=False)
def get_drive_file_metadata(file_id: str, token: str) -> dict:
    response = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"fields": "id,name,parents,mimeType,size"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(show_spinner=False)
def list_drive_children(folder_id: str, token: str) -> list[dict]:
    response = requests.get(
        "https://www.googleapis.com/drive/v3/files",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "q": f"'{folder_id}' in parents and trashed=false",
            "fields": "files(id,name,mimeType,size,parents,ownedByMe,owners(displayName,emailAddress,me))",
            "pageSize": 200,
            "orderBy": "name_natural",
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
        },
        timeout=30,
    )
    response.raise_for_status()
    files = response.json().get("files", [])
    return [
        item
        for item in files
        if item.get("mimeType") == FOLDER_MIME_TYPE
        or item.get("mimeType", "").startswith(IMAGE_MIME_PREFIX)
    ]


def sync_backend_session(access_token: str) -> str:
    existing_token = st.session_state.get("backend_access_token")
    existing_email = st.session_state.get("backend_user_email")
    if existing_token and existing_email == st.user.email:
        return existing_token

    payload = {
        "email": st.user.email,
        "name": getattr(st.user, "name", None),
        "avatar_url": getattr(st.user, "picture", None),
        "google_id": getattr(st.user, "sub", None),
        "drive_access_token": access_token,
    }
    response = requests.post(
        f"{BACKEND_URL}/auth/google/session",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    token_payload = response.json()
    backend_token = token_payload["access_token"]
    st.session_state["backend_access_token"] = backend_token
    st.session_state["backend_user_email"] = st.user.email
    return backend_token


def get_backend_headers(backend_token: str) -> dict:
    return {"Authorization": f"Bearer {backend_token}"}


def upsert_backend_folder(backend_token: str, folder_id: str, folder_name: str | None) -> dict:
    response = requests.post(
        f"{BACKEND_URL}/ingestion/folders",
        headers=get_backend_headers(backend_token),
        json={
            "drive_folder_id": folder_id,
            "folder_name": folder_name,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def start_backend_ingestion(backend_token: str, folder_row_id: str) -> dict:
    response = requests.post(
        f"{BACKEND_URL}/ingestion/folders/{folder_row_id}/start",
        headers=get_backend_headers(backend_token),
        json={"job_type": "full"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_ingestion_job(backend_token: str, job_id: str) -> dict:
    response = requests.get(
        f"{BACKEND_URL}/ingestion/jobs/{job_id}",
        headers=get_backend_headers(backend_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_all_ingested_images(backend_token: str) -> list[dict]:
    response = requests.get(
        f"{BACKEND_URL}/ingestion/images",
        headers=get_backend_headers(backend_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def search_backend_with_url(backend_token: str, image_url: str, file_name: str, limit: int) -> dict:
    image_response = requests.get(image_url, timeout=120)
    image_response.raise_for_status()
    return search_backend(
        backend_token,
        file_name=file_name,
        file_bytes=image_response.content,
        limit=limit,
    )


def search_backend(backend_token: str, file_name: str, file_bytes: bytes, limit: int) -> dict:
    response = requests.post(
        f"{BACKEND_URL}/search",
        headers=get_backend_headers(backend_token),
        params={"limit": limit},
        files={"image": (file_name, file_bytes)},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def get_drive_browser_state() -> tuple[list[str], str]:
    stack = st.session_state.setdefault("drive_browser_stack", ["root"])
    return stack, stack[-1]


def open_drive_folder(folder_id: str) -> None:
    stack, _ = get_drive_browser_state()
    st.session_state["drive_browser_stack"] = [*stack, folder_id]
    st.rerun()


def navigate_to_stack_index(index: int) -> None:
    stack, _ = get_drive_browser_state()
    st.session_state["drive_browser_stack"] = stack[: index + 1]
    st.rerun()


def go_to_parent_folder() -> None:
    stack, _ = get_drive_browser_state()
    if len(stack) > 1:
        st.session_state["drive_browser_stack"] = stack[:-1]
        st.rerun()


def go_to_root_folder() -> None:
    st.session_state["drive_browser_stack"] = ["root"]
    st.rerun()


def clear_drive_browser_cache() -> None:
    st.cache_data.clear()
    st.session_state.pop("manual_drive_folder_id", None)
    st.session_state.pop("manual_drive_folder_name", None)
    st.rerun()


def clear_backend_ingestion_state() -> None:
    st.session_state.pop("latest_ingestion_job_id", None)
    st.session_state.pop("latest_ingestion_job", None)
    st.session_state.pop("latest_search_response", None)
    st.rerun()


st.title("AI Image Classifier")

if not st.user.is_logged_in:
    st.write("Sign in with Google to continue.")
    if st.button("Authenticate with Google"):
        st.login("google")
else:
    st.success(f"Signed in as {st.user.email}.")
    st.write("Authentication successful! You can now use the AI Image Classifier.")

    access_token = st.user.tokens.get("access")
    if access_token:
        st.session_state["token"] = {"access_token": access_token}

    token_state = st.session_state.get("token", {})
    token = token_state.get("access_token")
    backend_token = None

    if not token:
        st.warning(
            "Google Drive access token is not available. Sign out and sign in again after updating the OAuth consent settings."
        )
    else:
        try:
            backend_token = sync_backend_session(token)
        except requests.RequestException as exc:
            st.session_state.pop("backend_access_token", None)
            st.error(f"Could not connect to backend at {BACKEND_URL}: {exc}")
            st.info("Drive browsing is still available, but ingestion and search need the backend to be running.")

        current_job = None
        current_job_status = None
        ingested_images: list[dict] = []
        if backend_token and st.session_state.get("latest_ingestion_job_id"):
            try:
                current_job = get_ingestion_job(
                    backend_token,
                    st.session_state["latest_ingestion_job_id"],
                )
                current_job_status = current_job.get("status")
                st.session_state["latest_ingestion_job"] = current_job
            except requests.RequestException as exc:
                st.error(f"Could not fetch ingestion job status: {exc}")

        if backend_token:
            try:
                ingested_images = get_all_ingested_images(backend_token)
            except requests.RequestException as exc:
                st.error(f"Could not fetch ingested files: {exc}")

        st.subheader("Google Drive")
        st.caption("This section shows live files from Google Drive, not rows from your database.")

        st.caption("Using the native Drive browser for folder selection.")

        stack, current_folder_id = get_drive_browser_state()
        breadcrumb_labels = []
        for folder_id in stack:
            if folder_id == "root":
                breadcrumb_labels.append({"id": folder_id, "name": "My Drive"})
            else:
                breadcrumb_labels.append(
                    {
                        "id": folder_id,
                        "name": get_drive_file_metadata(folder_id, token).get("name", folder_id),
                    }
                )

        nav_cols = st.columns([2, 2, 8])
        if nav_cols[0].button("My Drive", use_container_width=True):
            go_to_root_folder()
        if len(stack) > 1 and nav_cols[1].button("Up", use_container_width=True):
            go_to_parent_folder()
        breadcrumb_line = " / ".join(breadcrumb["name"] for breadcrumb in breadcrumb_labels)
        nav_cols[2].caption(f"Path: {breadcrumb_line}")

        drive_action_cols = st.columns([2, 3, 7])
        if drive_action_cols[0].button("Refresh Drive", use_container_width=True):
            clear_drive_browser_cache()
        drive_action_cols[1].caption("Clears cached Drive folder data and reloads this view.")

        if len(breadcrumb_labels) > 1:
            breadcrumb_cols = st.columns(len(breadcrumb_labels))
            for index, breadcrumb in enumerate(breadcrumb_labels):
                if breadcrumb_cols[index].button(
                    breadcrumb["name"],
                    key=f"breadcrumb_{breadcrumb['id']}_{index}",
                    use_container_width=True,
                ):
                    navigate_to_stack_index(index)

        try:
            current_children = list_drive_children(current_folder_id, token)
        except requests.RequestException as exc:
            current_children = []
            st.error(f"Could not list Google Drive folder contents: {exc}")

        current_folder_name = breadcrumb_labels[-1]["name"]
        st.write(f"Current folder: `{current_folder_name}`")
        st.caption(f"Items in this folder: {len(current_children)}")

        st.subheader("Folder Selection")
        st.write(
            f"Selected folder for ingestion: `{current_folder_name}` "
            f"(`{current_folder_id}`)"
        )
        manual_folder_id = st.text_input(
            "Or enter a Google Drive folder ID manually",
            value="",
            key="manual_drive_folder_id",
            placeholder="Paste a folder ID if browsing is empty",
        )
        manual_folder_name = st.text_input(
            "Manual folder name",
            value="",
            key="manual_drive_folder_name",
            placeholder="Optional display name",
        )

        folder_rows = [item for item in current_children if item.get("mimeType") == FOLDER_MIME_TYPE]
        file_rows = [
            item
            for item in current_children
            if item.get("mimeType", "").startswith(IMAGE_MIME_PREFIX)
        ]

        st.subheader("Folders")
        if folder_rows:
            for folder in folder_rows:
                folder_cols = st.columns([5, 2])
                folder_cols[0].write(f"[Folder] {folder['name']}")
                if folder_cols[1].button(
                    "Open",
                    key=f"open_folder_{folder['id']}",
                    use_container_width=True,
                ):
                    open_drive_folder(folder["id"])
        else:
            st.info("No subfolders found in this location.")

        browse_tab, ingested_tab = st.tabs(["Folder Photos", "Ingested Photos"])

        with browse_tab:
            st.subheader("Google Drive Photos")
            if file_rows:
                my_uploaded_rows = [item for item in file_rows if item.get("ownedByMe")]
                st.caption(f"Image files uploaded by you in this folder: {len(my_uploaded_rows)}")
                st.dataframe(
                    [
                        {
                            "filename": file_row.get("name"),
                            "mime_type": file_row.get("mimeType"),
                            "size_bytes": file_row.get("size", "unknown"),
                            "owner": ", ".join(
                                owner.get("emailAddress") or owner.get("displayName") or "unknown"
                                for owner in file_row.get("owners", [])
                            )
                            or "unknown",
                        }
                        for file_row in my_uploaded_rows
                    ],
                    use_container_width=True,
                )
            else:
                st.info("No image files found in this folder.")

        with ingested_tab:
            st.subheader("Backend Ingested Photos")
            st.caption("This tab is backed by `/ingestion/images` from the FastAPI backend.")
            if ingested_images:
                st.dataframe(
                    [
                        {
                            "filename": image_row.get("drive_file_name"),
                            "drive_file_id": image_row.get("drive_file_id"),
                            "mime_type": image_row.get("mime_type"),
                            "size_bytes": image_row.get("file_size_bytes"),
                            "ingested_status": image_row.get("status"),
                            "faces_found": image_row.get("face_count"),
                            "error": image_row.get("error_message"),
                        }
                        for image_row in ingested_images
                    ],
                    use_container_width=True,
                )
            else:
                st.info("No photos have been ingested yet.")

        if backend_token:
            st.subheader("Ingestion")
            ingest_action_cols = st.columns([2, 3, 7])
            if ingest_action_cols[0].button("Clear Ingestion State", use_container_width=True):
                clear_backend_ingestion_state()
            ingest_action_cols[1].caption("Clears saved job and search state from this Streamlit session.")
            if st.button("Ingest current folder", type="primary"):
                try:
                    chosen_folder_id = manual_folder_id.strip() or current_folder_id
                    chosen_folder_name = (
                        manual_folder_name.strip()
                        or (current_folder_name if current_folder_id != "root" else "My Drive")
                    )
                    folder_row = upsert_backend_folder(
                        backend_token,
                        folder_id=chosen_folder_id,
                        folder_name=chosen_folder_name,
                    )
                    job = start_backend_ingestion(backend_token, folder_row["id"])
                    st.session_state["latest_ingestion_job_id"] = job["id"]
                    st.success(f"Ingestion started for {chosen_folder_name}.")
                    st.rerun()
                except requests.RequestException as exc:
                    st.error(f"Failed to start ingestion: {exc}")

        if backend_token and st.session_state.get("latest_ingestion_job_id"):
            st.subheader("Ingestion Status")
            if st.button("Refresh job status"):
                st.cache_data.clear()
                st.rerun()
            if current_job:
                st.json(current_job)

        queryable_images = [
            image_row
            for image_row in ingested_images
            if image_row.get("status") == "done" and image_row.get("image_url")
        ]
        can_query = bool(backend_token and queryable_images)
        if can_query:
            st.subheader("Face Search")
            upload_query_tab, my_photos_query_tab = st.tabs(
                ["Upload Query Photo", "Use Ingested Photo"]
            )

            with upload_query_tab:
                query_file = st.file_uploader(
                    "Upload a query image",
                    type=["png", "jpg", "jpeg"],
                    key="query_image",
                )
                search_limit = st.slider(
                    "Search results",
                    min_value=1,
                    max_value=20,
                    value=10,
                    key="upload_query_limit",
                )
                if query_file and st.button("Search Using Uploaded Photo"):
                    try:
                        query_bytes = query_file.getvalue()
                        search_payload = search_backend(
                            backend_token,
                            file_name=query_file.name,
                            file_bytes=query_bytes,
                            limit=search_limit,
                        )
                        st.session_state["latest_search_response"] = search_payload
                    except requests.RequestException as exc:
                        st.error(f"Search failed: {exc}")

            with my_photos_query_tab:
                image_options = {
                    f"{image_row.get('drive_file_name') or image_row.get('drive_file_id')} ({image_row.get('drive_file_id')})": image_row
                    for image_row in queryable_images
                }
                selected_label = st.selectbox(
                    "Choose an ingested photo to use as the query image",
                    options=list(image_options.keys()),
                    key="query_from_ingested_photo",
                )
                query_limit = st.slider(
                    "Query results",
                    min_value=1,
                    max_value=20,
                    value=10,
                    key="query_from_ingested_photo_limit",
                )
                if st.button("Search Using Selected Photo"):
                    selected_image = image_options[selected_label]
                    try:
                        search_payload = search_backend_with_url(
                            backend_token,
                            image_url=selected_image["image_url"],
                            file_name=selected_image.get("drive_file_name") or "query.jpg",
                            limit=query_limit,
                        )
                        st.session_state["latest_search_response"] = search_payload
                    except requests.RequestException as exc:
                        st.error(f"Search failed: {exc}")
        elif backend_token and st.session_state.get("latest_ingestion_job_id"):
            st.info("Face search will unlock after ingestion completes successfully.")
        elif backend_token:
            st.info("Ingest at least one photo before running face search.")

        latest_search = st.session_state.get("latest_search_response")
        if latest_search:
            st.subheader("Search Results")
            st.write(
                f"Face detected: {latest_search['face_detected']} | "
                f"Results: {latest_search['results_count']} | "
                f"Latency: {latest_search['search_latency_ms']} ms"
            )
            results_table_tab, results_gallery_tab = st.tabs(["Results Table", "Result Photos"])
            with results_table_tab:
                if latest_search["results"]:
                    st.dataframe(
                        [
                            {
                                "rank": item["rank"],
                                "score": item["similarity_score"],
                                "image_name": item["image_name"],
                                "drive_file_id": item["drive_file_id"],
                            }
                            for item in latest_search["results"]
                        ],
                        use_container_width=True,
                    )
                else:
                    st.info("No similar faces were found for this query.")

            with results_gallery_tab:
                image_results = [item for item in latest_search["results"] if item.get("image_url")]
                if image_results:
                    for item in image_results:
                        st.markdown(
                            f"Rank {item['rank']} | Score {item['similarity_score']:.4f} | {item.get('image_name') or item.get('drive_file_id')}"
                        )
                        st.image(item["image_url"], use_container_width=True)
                else:
                    st.info("No displayable result photos were available.")

    if st.button("Log out"):
        st.session_state.pop("backend_access_token", None)
        st.session_state.pop("backend_user_email", None)
        st.session_state.pop("drive_browser_stack", None)
        st.session_state.pop("latest_ingestion_job_id", None)
        st.session_state.pop("latest_ingestion_job", None)
        st.session_state.pop("latest_search_response", None)
        st.logout()
