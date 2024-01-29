try:
    from github import Github, Repository, GitRef
except:
    print("Please install PyGithub using the command: pip install PyGithub")
    raise


class KCBranch (object):
    def __init__(self, repo: 'KCRepo', branch: GitRef, branch_name: str) -> None:
        self.__repo = repo
        self.__branch = branch
        self.__branch_name = branch_name

    def create_branch(self, branch_name: str) -> 'KCBranch':
        # Create a new branch based on the latest commit of the base branch
        branch = self.__repo.git_repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=self.__branch.object.sha)
        return KCBranch(self.__repo, branch, branch_name)
    
    def create_tag(self, tag_name: str, tag_message: str):
        # Create a new tag
        tag = self.__repo.git_repo.create_git_tag(tag_name, tag_message, self.__branch.object.sha, 'commit')

    def create_release(self, tag_name, release_name, release_message):
        self.__repo.git_repo.create_git_release(
            tag_name,
            release_name,
            release_message,
            target_commitish=self.__branch_name,
        )
    
    def create_tag_and_release(self, tag_name: str, tag_message: str, release_name: str, release_message: str):
        # Create a new tag
        tag = self.create_tag(tag_name, tag_message)
        # Release the tag
        self.create_release(tag_name, release_name, release_message)


class KCRepo (object):
    def __init__(self, repo: Repository) -> None:
        self.__repo = repo
    
    @property
    def git_repo(self) -> Repository:
        return self.__repo
    
    def get_branch(self, branch_name: str) -> KCBranch:
        ref = self.__repo.get_git_ref(f"heads/{branch_name}")
        return KCBranch(self, ref, branch_name)
    
    def list_branches(self):
        print(list(self.__repo.get_branches()))
    

class KCGit:
    ACCESS_TOKEN = 'xxxxxxxxxxxxxxxxxxxxxx'

    def __init__(self) -> None:
        self._git_conn = Github(base_url="https://github.com/api/v3", login_or_token=self.ACCESS_TOKEN)
    
    def get_repo(self, repo_name: str) -> KCRepo:
        repo = self._git_conn.get_organization("netbrain").get_repo( repo_name )
        return KCRepo(repo)
    
    def release(self, repo_name: str, base_branch_name: str, release_branch_name: str, tag_name: str, tag_message: str, release_name: str, release_message: str) -> bool:
        try:
            print("\t\tGetting the repository %s" % repo_name)
            repo = self.get_repo(repo_name)
        except Exception as ex:
            print("\t\tFailed to get the repository: %s, exception: %s" % (repo_name, ex))
            return False

        try:
            print("\t\tGetting the branch %s" % base_branch_name)
            branch = repo.get_branch(base_branch_name)
        except Exception as ex:
            print("\t\tFailed to get the branch: %s, exception: %s" % (base_branch_name, ex))
            return False

        try:
            print("\t\tCreating the branch %s" % release_branch_name)
            target_branch = branch.create_branch(release_branch_name)
        except Exception as ex:
            print("\t\tFailed to create the branch: %s, exception: %s" % (release_branch_name, ex))
            return False
        
        try:
            print("\t\tCreating the tag %s" % tag_name)
            target_branch.create_tag_and_release(tag_name, tag_message, release_name, release_message)
        except Exception as ex:
            print("\t\tFailed to create the tag: %s, exception: %s" % (tag_name, ex))
            return False
        
        return True
    
    def get_release_note(self, version) -> str:
        release_note = ''
        file_name = version + '_Release_Note.txt'
        try:
            with open(file_name) as content:
                release_note = content.read()
        except:
            print('Get release note failed.')
        finally:
            pass
        return release_note
    
    def load_repository_names(self, file_path: str):
        names = []
        with open(file_path) as f:
            for line in f:
                name = line.strip()
                if not name:
                    continue
                
                names.append(name)
        names.sort()
        return names
    
    def release_10_1_15(self) -> bool:
        file_path = '10.1.15_Repos.txt'
        repo_names = self.load_repository_names(file_path)

        print("There are %d repositories in the verion 10.1.15 need to be released" % len(repo_names))

        from_branch = 'dev_10.1.15'
        to_branch = 'release_10.1.15'
        tag_name = 'release_10.1.15/v0.15.1'
        tag_message = ''
        release_name = 'release_10.1.15/v0.15.1'
        release_message = self.get_release_note('10.1.15')

        idx = 0
        failed_repos = []
        for repo_name in repo_names:
            print("%d: releasing the repository %s" % (idx, repo_name))
            ret = self.release(repo_name, from_branch, to_branch, tag_name, tag_message, release_name, release_message)
            if ret:
                print("\tSuccessfully release the repository %s" % repo_name)
            else:
                print("\tFailed to release the repository %s" % repo_name)
                failed_repos.append(repo_name)
            idx = idx + 1

        if failed_repos:
            print("\nFailed to be released repositories:")
            for repo_name in failed_repos:
                print(repo_name)
        print("\nSucceed: %d, Failed: %d" % (len(repo_names) - len(failed_repos), len(failed_repos)))



if __name__ == "__main__":
    kcgit = KCGit()
    kcgit.release_10_1_15()