#!/bin/bash
export TERM=xterm

USER_DB="users.json"
STORAGE_ROOT="/mnt/shared/ftpshare"

banner() {
    echo "-------------------------------------------"
    echo "$1"
    echo "-------------------------------------------"
}

pause() {
    read -p "Press Enter to continue..."
}

show_users() {
    banner "Current Users"
    jq -r 'keys[]' $USER_DB
    echo
    pause
}

add_user() {
    banner "Add New User"

    read -p "Enter new username: " USER
    read -sp "Enter password: " PASS; echo
    read -p "Is admin? (y/n): " ADMIN_CHOICE

    if [[ "$ADMIN_CHOICE" == "y" ]]; then
        ADMIN=true
    else
        ADMIN=false
    fi

    if jq -e ".\"$USER\"" $USER_DB >/dev/null; then
        banner "User already exists!"
        pause
        return
    fi

    jq ". + {\"$USER\": {\"password\": \"$PASS\", \"is_admin\": $ADMIN}}" $USER_DB > tmp.$$.json \
        && mv tmp.$$.json $USER_DB

    mkdir -p "$STORAGE_ROOT/$USER"

    banner "User '$USER' added successfully."
    pause
}

change_password() {
    banner "Change Password"

    read -p "Enter username: " USER

    if ! jq -e ".\"$USER\"" $USER_DB >/dev/null; then
        banner "User does not exist!"
        pause
        return
    fi

    read -sp "Enter new password: " PASS; echo

    jq ".\"$USER\".password = \"$PASS\"" $USER_DB > tmp.$$.json \
        && mv tmp.$$.json $USER_DB

    banner "Password updated for '$USER'."
    pause
}

delete_user_login() {
    banner "Delete User (Login Only)"

    read -p "Enter username: " USER

    if ! jq -e ".\"$USER\"" $USER_DB >/dev/null; then
        banner "User does not exist!"
        pause
        return
    fi

    jq "del(.\"$USER\")" $USER_DB > tmp.$$.json \
        && mv tmp.$$.json $USER_DB

    banner "User '$USER' login removed. User folder NOT removed."
    pause
}

delete_user_full() {
    banner "Delete User + User Folder"

    read -p "Enter username: " USER

    if ! jq -e ".\"$USER\"" $USER_DB >/dev/null; then
        banner "User does not exist!"
        pause
        return
    fi

    # Remove login
    jq "del(.\"$USER\")" $USER_DB > tmp.$$.json \
        && mv tmp.$$.json $USER_DB

    # Remove folder if exists
    USER_DIR="$STORAGE_ROOT/$USER"
    if [[ -d "$USER_DIR" ]]; then
        rm -rf "$USER_DIR"
        banner "User '$USER' login removed AND folder deleted ($USER_DIR)"
    else
        banner "User login removed. But folder did NOT exist ($USER_DIR)"
    fi

    pause
}

menu() {
    while true; do
        clear
        echo "============ FTP USER MANAGEMENT ============"
        echo "1) Show all users"
        echo "2) Add user"
        echo "3) Change password"
        echo "4) Delete user (login only)"
        echo "5) Delete user + folder"
        echo "6) Exit"
        echo "============================================="
        read -p "Enter choice: " CH

        case "$CH" in
            1) show_users ;;
            2) add_user ;;
            3) change_password ;;
            4) delete_user_login ;;
            5) delete_user_full ;;
            6) banner "Goodbye!"; exit 0 ;;
            *) echo "Invalid choice"; sleep 1 ;;
        esac
    done
}

menu
