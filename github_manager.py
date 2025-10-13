"""
GitHub Manager - Tự động push code lên GitHub
"""
import requests
import base64
import json
from typing import Dict, List, Optional
import time


class GitHubManager:
    """Manager để tương tác với GitHub API"""
    
    def __init__(self, github_token: str, username: str):
        self.token = github_token
        self.username = username
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def create_repository(self, repo_name: str, description: str = "", private: bool = False) -> Dict:
        """Tạo repository mới trên GitHub"""
        url = f"{self.api_base}/user/repos"
        data = {
            "name": repo_name,
            "description": description,
            "private": private,
            "auto_init": False
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code == 201:
            return response.json()
        elif response.status_code == 422:
            # Repository already exists
            return self.get_repository(repo_name)
        else:
            raise Exception(f"Lỗi tạo repository: {response.json()}")
    
    def get_repository(self, repo_name: str) -> Dict:
        """Lấy thông tin repository"""
        url = f"{self.api_base}/repos/{self.username}/{repo_name}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Repository không tồn tại: {repo_name}")
    
    def create_or_update_file(self, repo_name: str, file_path: str, content: str, 
                              message: str, branch: str = "main") -> Dict:
        """Tạo hoặc cập nhật file trong repository"""
        url = f"{self.api_base}/repos/{self.username}/{repo_name}/contents/{file_path}"
        
        # Kiểm tra file có tồn tại không
        existing_file = None
        response = requests.get(url, headers=self.headers, params={"ref": branch})
        if response.status_code == 200:
            existing_file = response.json()
        
        # Encode content to base64
        content_encoded = base64.b64encode(content.encode()).decode()
        
        data = {
            "message": message,
            "content": content_encoded,
            "branch": branch
        }
        
        if existing_file:
            data["sha"] = existing_file["sha"]
        
        response = requests.put(url, headers=self.headers, json=data)
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            raise Exception(f"Lỗi tạo/cập nhật file {file_path}: {response.json()}")
    
    def push_files_batch(self, repo_name: str, files: Dict[str, str], 
                        commit_message: str = "Initial commit from Dev Portal",
                        branch: str = "main") -> Dict:
        """Push nhiều files lên repository trong 1 commit duy nhất sử dụng Git Tree API"""
        try:
            # Đợi một chút để đảm bảo repo được tạo xong
            time.sleep(2)
            
            # 1. Get latest commit SHA
            ref_url = f"{self.api_base}/repos/{self.username}/{repo_name}/git/refs/heads/{branch}"
            ref_response = requests.get(ref_url, headers=self.headers)
            
            if ref_response.status_code != 200:
                # Nếu branch chưa tồn tại, tạo commit đầu tiên
                return self._create_initial_commit(repo_name, files, commit_message)
            
            latest_commit_sha = ref_response.json()["object"]["sha"]
            
            # 2. Get commit details
            commit_url = f"{self.api_base}/repos/{self.username}/{repo_name}/git/commits/{latest_commit_sha}"
            commit_response = requests.get(commit_url, headers=self.headers)
            base_tree_sha = commit_response.json()["tree"]["sha"]
            
            # 3. Create tree với tất cả files
            import base64
            tree_items = []
            for file_path, content in files.items():
                content_encoded = base64.b64encode(content.encode()).decode()
                tree_items.append({
                    "path": file_path,
                    "mode": "100644",
                    "type": "blob",
                    "content": content_encoded
                })
            
            tree_data = {
                "base_tree": base_tree_sha,
                "tree": tree_items
            }
            
            # 4. Create tree
            tree_url = f"{self.api_base}/repos/{self.username}/{repo_name}/git/trees"
            tree_response = requests.post(tree_url, headers=self.headers, json=tree_data)
            
            if tree_response.status_code != 201:
                raise Exception(f"Failed to create tree: {tree_response.json()}")
            
            new_tree_sha = tree_response.json()["sha"]
            
            # 5. Create commit
            commit_data = {
                "message": commit_message,
                "tree": new_tree_sha,
                "parents": [latest_commit_sha]
            }
            
            commit_url = f"{self.api_base}/repos/{self.username}/{repo_name}/git/commits"
            commit_response = requests.post(commit_url, headers=self.headers, json=commit_data)
            
            if commit_response.status_code != 201:
                raise Exception(f"Failed to create commit: {commit_response.json()}")
            
            new_commit_sha = commit_response.json()["sha"]
            
            # 6. Update branch reference
            update_ref_data = {
                "sha": new_commit_sha
            }
            
            update_ref_response = requests.patch(ref_url, headers=self.headers, json=update_ref_data)
            
            if update_ref_response.status_code != 200:
                raise Exception(f"Failed to update branch: {update_ref_response.json()}")
            
            return {
                "status": "success",
                "commit_sha": new_commit_sha,
                "files_count": len(files),
                "message": f"Successfully pushed {len(files)} files in 1 commit"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "fallback_to_individual": True
            }
    
    def _create_initial_commit(self, repo_name: str, files: Dict[str, str], commit_message: str) -> Dict:
        """Tạo commit đầu tiên cho repository mới"""
        try:
            # 1. Create tree với tất cả files
            import base64
            tree_items = []
            for file_path, content in files.items():
                content_encoded = base64.b64encode(content.encode()).decode()
                tree_items.append({
                    "path": file_path,
                    "mode": "100644",
                    "type": "blob",
                    "content": content_encoded
                })
            
            tree_data = {
                "tree": tree_items
            }
            
            tree_url = f"{self.api_base}/repos/{self.username}/{repo_name}/git/trees"
            tree_response = requests.post(tree_url, headers=self.headers, json=tree_data)
            
            if tree_response.status_code != 201:
                raise Exception(f"Failed to create initial tree: {tree_response.json()}")
            
            tree_sha = tree_response.json()["sha"]
            
            # 2. Create commit
            commit_data = {
                "message": commit_message,
                "tree": tree_sha
            }
            
            commit_url = f"{self.api_base}/repos/{self.username}/{repo_name}/git/commits"
            commit_response = requests.post(commit_url, headers=self.headers, json=commit_data)
            
            if commit_response.status_code != 201:
                raise Exception(f"Failed to create initial commit: {commit_response.json()}")
            
            commit_sha = commit_response.json()["sha"]
            
            # 3. Create main branch reference (for new repo without auto_init)
            ref_url = f"{self.api_base}/repos/{self.username}/{repo_name}/git/refs"
            ref_data = {
                "ref": "refs/heads/main",
                "sha": commit_sha
            }
            
            ref_response = requests.post(ref_url, headers=self.headers, json=ref_data)
            
            if ref_response.status_code not in [201, 200]:
                raise Exception(f"Failed to create main branch: {ref_response.json()}")
            
            return {
                "status": "success",
                "commit_sha": commit_sha,
                "files_count": len(files),
                "message": f"Successfully created initial commit with {len(files)} files"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def push_files(self, repo_name: str, files: Dict[str, str], 
                   commit_message: str = "Initial commit from Dev Portal",
                   branch: str = "main") -> List[Dict]:
        """Push nhiều files lên repository - thử batch trước, fallback individual"""
        # Thử batch push trước
        batch_result = self.push_files_batch(repo_name, files, commit_message, branch)
        
        if batch_result["status"] == "success":
            # Batch thành công - chỉ có 1 commit, 1 workflow run
            return [{
                "file": "batch_push",
                "status": "success",
                "message": batch_result["message"],
                "commit_sha": batch_result["commit_sha"]
            }]
        else:
            # Batch thất bại - fallback về individual push
            print(f"Batch push failed: {batch_result['error']}, falling back to individual push")
            return self._push_files_individual(repo_name, files, commit_message, branch)
    
    def _push_files_individual(self, repo_name: str, files: Dict[str, str], 
                              commit_message: str, branch: str) -> List[Dict]:
        """Fallback: Push từng file riêng lẻ"""
        results = []
        
        for file_path, content in files.items():
            try:
                result = self.create_or_update_file(
                    repo_name=repo_name,
                    file_path=file_path,
                    content=content,
                    message=commit_message,
                    branch=branch
                )
                results.append({
                    "file": file_path,
                    "status": "success",
                    "url": result.get("content", {}).get("html_url", "")
                })
                time.sleep(0.1)
            except Exception as e:
                results.append({
                    "file": file_path,
                    "status": "error",
                    "error": str(e)
                })
        
        return results
    
    def create_repository_and_push(self, repo_name: str, files: Dict[str, str],
                                   description: str = "", private: bool = False) -> Dict:
        """Tạo repository và push code một lần"""
        # Tạo hoặc lấy repository
        repo = self.create_repository(repo_name, description, private)
        
        # Push files
        push_results = self.push_files(repo_name, files)
        
        success_count = sum(1 for r in push_results if r["status"] == "success")
        error_count = sum(1 for r in push_results if r["status"] == "error")
        
        return {
            "repository": {
                "name": repo["name"],
                "full_name": repo["full_name"],
                "html_url": repo["html_url"],
                "clone_url": repo["clone_url"],
                "ssh_url": repo["ssh_url"]
            },
            "push_results": {
                "total": len(push_results),
                "success": success_count,
                "error": error_count,
                "details": push_results
            }
        }
    
    def update_repository_b_manifests(self, repo_b_name: str, app_name: str, 
                                      manifests: Dict[str, str]) -> Dict:
        """Cập nhật K8s manifests trong Repository_B với multi-app structure"""
        results = []
        
        # Files cần SKIP (không push vào apps/)
        skip_files = [
            'argocd-application.yaml',  # ApplicationSet tự tạo
            'argocd-image-updater-config.yaml',  # Không cần
            'README.md'  # Documentation
        ]
        
        # Push manifests vào apps/<app-name>/ directory (multi-app structure)
        for file_name, content in manifests.items():
            # SKIP các file không cần update
            if file_name in skip_files:
                continue
            
            # Tất cả manifests vào apps/<app-name>/
            file_path = f"apps/{app_name}/{file_name}"
            
            try:
                result = self.create_or_update_file(
                    repo_name=repo_b_name,
                    file_path=file_path,
                    content=content,
                    message=f"Update {app_name}/{file_name} from Dev Portal"
                )
                results.append({
                    "file": file_path,
                    "status": "success",
                    "url": result.get("content", {}).get("html_url", "")
                })
                time.sleep(0.5)
            except Exception as e:
                results.append({
                    "file": file_path,
                    "status": "error",
                    "error": str(e)
                })
        
        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = sum(1 for r in results if r["status"] == "error")
        
        return {
            "total": len(results),
            "success": success_count,
            "error": error_count,
            "details": results
        }
    
    def add_repository_secret(self, repo_name: str, secret_name: str, secret_value: str) -> Dict:
        """Add secret to repository for GitHub Actions"""
        try:
            # Import thư viện để encrypt
            from base64 import b64encode
            from nacl import encoding, public
            
            # 1. Get repository public key
            key_url = f"{self.api_base}/repos/{self.username}/{repo_name}/actions/secrets/public-key"
            key_response = requests.get(key_url, headers=self.headers)
            
            if key_response.status_code != 200:
                return {"status": "error", "message": f"Failed to get public key: {key_response.status_code}"}
            
            public_key_data = key_response.json()
            public_key = public.PublicKey(public_key_data["key"].encode("utf-8"), encoding.Base64Encoder())
            
            # 2. Encrypt secret value
            sealed_box = public.SealedBox(public_key)
            encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
            encrypted_value = b64encode(encrypted).decode("utf-8")
            
            # 3. Add/Update secret
            secret_url = f"{self.api_base}/repos/{self.username}/{repo_name}/actions/secrets/{secret_name}"
            data = {
                "encrypted_value": encrypted_value,
                "key_id": public_key_data["key_id"]
            }
            
            response = requests.put(secret_url, headers=self.headers, json=data)
            
            if response.status_code in [201, 204]:
                return {"status": "success", "message": f"Secret {secret_name} added successfully"}
            else:
                return {"status": "error", "message": f"Failed to add secret: {response.status_code}"}
        
        except ImportError:
            return {"status": "error", "message": "PyNaCl library required. Install: pip install PyNaCl"}
        except Exception as e:
            return {"status": "error", "message": f"Error adding secret: {str(e)}"}
    
    def trigger_workflow(self, repo_name: str, workflow_file: str = "ci-cd.yml", 
                        branch: str = "main") -> Dict:
        """Trigger GitHub Actions workflow"""
        url = f"{self.api_base}/repos/{self.username}/{repo_name}/actions/workflows/{workflow_file}/dispatches"
        data = {
            "ref": branch
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code == 204:
            return {"status": "success", "message": "Workflow triggered successfully"}
        else:
            return {"status": "error", "message": f"Failed to trigger workflow: {response.status_code}"}
    
    def get_latest_workflow_run(self, repo_name: str, workflow_file: str = "ci-cd.yml") -> Dict:
        """Get latest workflow run status"""
        try:
            url = f"{self.api_base}/repos/{self.username}/{repo_name}/actions/workflows/{workflow_file}/runs"
            response = requests.get(url, headers=self.headers, params={"per_page": 1})
            
            if response.status_code == 200:
                data = response.json()
                if data["total_count"] > 0:
                    run = data["workflow_runs"][0]
                    return {
                        "status": "success",
                        "run_id": run["id"],
                        "run_status": run["status"],  # queued, in_progress, completed
                        "conclusion": run["conclusion"],  # success, failure, cancelled, null
                        "html_url": run["html_url"],
                        "created_at": run["created_at"],
                        "updated_at": run["updated_at"]
                    }
                else:
                    return {"status": "error", "message": "No workflow runs found"}
            else:
                return {"status": "error", "message": f"Failed to get workflow runs: {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}
    
    def wait_for_workflow_completion(self, repo_name: str, workflow_file: str = "ci-cd.yml", 
                                     timeout: int = 600, check_interval: int = 10) -> Dict:
        """
        Wait for workflow to complete with timeout
        
        Args:
            repo_name: Repository name
            workflow_file: Workflow filename
            timeout: Maximum wait time in seconds (default 10 minutes)
            check_interval: Check interval in seconds (default 10 seconds)
        
        Returns:
            Dict with status and workflow info
        """
        import time
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            result = self.get_latest_workflow_run(repo_name, workflow_file)
            
            if result["status"] == "error":
                return result
            
            run_status = result["run_status"]
            conclusion = result["conclusion"]
            
            # Check if workflow completed
            if run_status == "completed":
                if conclusion == "success":
                    return {
                        "status": "success",
                        "message": "Workflow completed successfully",
                        "run_id": result["run_id"],
                        "html_url": result["html_url"],
                        "duration": int(time.time() - start_time)
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Workflow failed with conclusion: {conclusion}",
                        "run_id": result["run_id"],
                        "html_url": result["html_url"]
                    }
            
            # Still in progress
            time.sleep(check_interval)
        
        # Timeout
        return {
            "status": "timeout",
            "message": f"Workflow did not complete within {timeout} seconds",
            "run_status": run_status
        }

