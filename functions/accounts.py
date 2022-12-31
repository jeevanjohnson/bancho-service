from repositories.accounts import AccountRepo


def generate_user_id(account_repo: AccountRepo) -> int:
    accounts = account_repo.fetch_all()

    if not accounts:
        return 4
    else:
        return len(accounts) + 4
