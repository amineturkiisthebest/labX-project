import { useState, useEffect } from "react";
import "./manageusers.css";
import { useNavigate } from "react-router-dom";

function ManageUsers() {
    const navigate = useNavigate();
    const [users, setUsers] = useState([]);
    const [showModal, setShowModal] = useState(false);
    const [ErrorEmail, setErrorEmail] = useState("");
    const [ErrorUsername, setErrorUsername] = useState("");
    const [editUserId, setEditUserId] = useState("");
    const [editUsername, setEditUsername] = useState("");
    const [editEmail, setEditEmail] = useState("");
    const [editRole, setEditRole] = useState("");
    const [editPassword, setEditPassword] = useState("");
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [userToDelete, setUserToDelete] = useState(null);

    const handleEditClick = (user) => {
        setEditUserId(user._id);
        setEditUsername(user.username);
        setEditEmail(user.email);
        setEditRole(user.role);
        setEditPassword(user.password);
        setErrorUsername("");
        setErrorEmail("");
        setShowModal(true);
    };

    const handleEditSubmit = async (e) => {
        e.preventDefault();
        // TODO: add backend fetch call here to update the user
        const response = await fetch("http://localhost:8000/edit_user", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ editUserId, editUsername, editEmail, editRole, editPassword }),
        });
        const data = await response.json();
        if (data.messageErrorEmail) {
            setErrorEmail(data.messageErrorEmail);
            setErrorUsername("");
        }
        if (data.messageErrorUsername) {
            setErrorEmail("");
            setErrorUsername(data.messageErrorUsername);
        }
        if (data.message) {
            setErrorEmail("");
            setErrorUsername("");
            setShowModal(false);
            fetchUsers();
        }
    };

    const handleDeleteClick = (user) => {
        setUserToDelete(user);
        setShowDeleteModal(true);
    };

    const handleConfirmDelete = async () => {
        if (userToDelete) {
            const response = await fetch("http://localhost:8000/delete_user", {
                method: "DELETE",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ userId: userToDelete._id }),
            });
            setShowDeleteModal(false);
            setUserToDelete(null);
            fetchUsers();
        }
    };

    const handleLogout = () => {
        localStorage.removeItem("token");
        localStorage.removeItem("email");
        localStorage.removeItem("role");
        navigate("/");
    };

    const handleReturnHome = () => {
        navigate("/home");
    };
    const fetchUsers = async () => {
        const response = await fetch("http://localhost:8000/manageusers");
        const data = await response.json();
        setUsers(data.users);
    };

    const token = localStorage.getItem("token");
    const role = localStorage.getItem("role");

    useEffect(() => {
        fetchUsers();
        if (!token) {
            navigate("/");
        } else if (role && role.toLowerCase() !== "administrator") {
            navigate("/home");
        }
    }, [token, role, navigate]);

    return (
        <div className="manageusers-container">
            <div className="background-image"></div>

            <nav className="glass-nav">
                <div className="nav-logo" onClick={handleReturnHome} style={{ cursor: "pointer" }}>LabX</div>
                <div style={{ display: "flex", gap: "12px" }}>
                    <button onClick={handleReturnHome} className="logout-btn" style={{ borderColor: 'rgba(255, 255, 255, 0.2)' }}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                            <polyline points="9 22 9 12 15 12 15 22"></polyline>
                        </svg>
                        <span>Return Home</span>
                    </button>
                    <button onClick={handleLogout} className="logout-btn">
                        <span>Log Out</span>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                            <polyline points="16 17 21 12 16 7"></polyline>
                            <line x1="21" y1="12" x2="9" y2="12"></line>
                        </svg>
                    </button>
                </div>
            </nav>

            <main className="manageusers-content">
                <header className="manageusers-header">
                    <h1>Manage Users</h1>
                    <p>View and manage researcher permissions and accounts.</p>
                </header>

                <div className="manageusers-actions">
                    <button className="add-user-btn" onClick={() => navigate("/signup")}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                            <circle cx="8.5" cy="7" r="4"></circle>
                            <line x1="20" y1="8" x2="20" y2="14"></line>
                            <line x1="23" y1="11" x2="17" y2="11"></line>
                        </svg>
                        <span>Add New User</span>
                    </button>
                </div>

                <div className="users-table-container">
                    <table className="users-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Role</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {users.map((user) => (
                                <tr key={user._id}>
                                    <td>
                                        <div className="user-info">
                                            <div className="user-avatar">
                                                {user.username.charAt(0)}
                                            </div>
                                            <span>{user.username}</span>
                                        </div>
                                    </td>
                                    <td>{user.email}</td>
                                    <td>
                                        <span className={`role-badge ${user.role.toLowerCase()}`}>
                                            {user.role}
                                        </span>
                                    </td>
                                    <td>
                                        <button className="action-btn edit-btn" onClick={() => handleEditClick(user)}>Edit</button>
                                        <button className="action-btn delete-btn" onClick={() => handleDeleteClick(user)}>Delete</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </main>

            {showModal && (
                <div className="modal-overlay">
                    <div className="modal-card">
                        <h2>Edit User</h2>
                        <form onSubmit={handleEditSubmit}>
                            <div className="form-group">
                                <label htmlFor="edit-username">Username</label>
                                {ErrorUsername && <p className="error-label">{ErrorUsername}</p>}
                                <div className="input-wrapper">
                                    <input
                                        type="text"
                                        id="edit-username"
                                        value={editUsername}
                                        onChange={(e) => setEditUsername(e.target.value)}
                                        required
                                    />
                                </div>
                            </div>
                            <div className="form-group">
                                <label htmlFor="edit-email">Email</label>
                                {ErrorEmail && <p className="error-label">{ErrorEmail}</p>}
                                <div className="input-wrapper">
                                    <input
                                        type="email"
                                        id="edit-email"
                                        value={editEmail}
                                        onChange={(e) => setEditEmail(e.target.value)}
                                        required
                                    />
                                </div>
                            </div>
                            <div className="form-group">
                                <label htmlFor="edit-role">Role</label>
                                <div className="input-wrapper">
                                    <select
                                        id="edit-role"
                                        value={editRole}
                                        onChange={(e) => setEditRole(e.target.value)}
                                        className="role-select"
                                    >
                                        <option value="Researcher">Researcher</option>
                                        <option value="Administrator">Administrator</option>
                                        <option value="Normal User">Normal User</option>
                                    </select>
                                </div>
                            </div>
                            <div className="form-group">
                                <label htmlFor="edit-password">New Password (leave keep current)</label>
                                <div className="input-wrapper">
                                    <input
                                        type="password"
                                        id="edit-password"
                                        value={editPassword}
                                        onChange={(e) => setEditPassword(e.target.value)}
                                    />
                                </div>
                            </div>
                            <div className="modal-actions">
                                <button type="button" className="cancel-btn" onClick={() => setShowModal(false)}>Cancel</button>
                                <button type="submit" className="create-btn">Save Changes</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {showDeleteModal && (
                <div className="modal-overlay">
                    <div className="modal-card">
                        <h2>Confirm Delete</h2>
                        <p style={{ color: "var(--text-muted)", marginBottom: "24px" }}>
                            Are you sure you want to delete user <strong>{userToDelete?.username}</strong>? This action cannot be undone.
                        </p>
                        <div className="modal-actions">
                            <button type="button" className="cancel-btn" onClick={() => setShowDeleteModal(false)}>Cancel</button>
                            <button type="button" className="delete-confirm-btn" onClick={handleConfirmDelete}>Delete</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default ManageUsers;
