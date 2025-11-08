
import sqlite3
import hashlib

def change_admin_password():
    
    print("=" * 60)
    print("Cellar Society - Change Admin Password")
    print("=" * 60)
    
    # Get current username
    username = input("Enter admin username (default: admin): ").strip()
    if not username:
        username = "admin"
    
    # Get new password
    new_password = input("Enter NEW password: ").strip()
    
    if not new_password:
        print("Password cannot be empty!")
        return
    
    # Confirm password
    confirm_password = input("Confirm NEW password: ").strip()
    
    if new_password != confirm_password:
        print("Passwords don't match!")
        return

    # Hash the new password
    hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
    
    # Update database
    try:
        conn = sqlite3.connect('cellar_society.db')
        c = conn.cursor()
        
        # Check if admin exists
        c.execute("SELECT * FROM admins WHERE username = ?", (username,))
        admin = c.fetchone()
        
        if not admin:
            print(f"Admin '{username}' not found!")
            conn.close()
            return
        
        # Update password
        c.execute("UPDATE admins SET password = ? WHERE username = ?",
                 (hashed_password, username))
        conn.commit()
        conn.close()
        
        print("=" * 60)
        print(f"Password changed successfully for '{username}'!")
        print("=" * 60)
        print("New credentials:")
        print(f"   Username: {username}")
        print(f"   Password: {new_password}")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    change_admin_password()