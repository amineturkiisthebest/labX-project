import { useState, useEffect, useRef } from "react";
import "./home.css";
import { useNavigate } from "react-router-dom";

function Home() {
    const navigate = useNavigate();
    const [showModal, setShowModal] = useState(false);
    const [newWorkspaceName, setNewWorkspaceName] = useState("");
    const [newWorkspaceDescription, setNewWorkspaceDescription] = useState("");
    const [messageError, setMessageError] = useState("");
    const [workspaces, setWorkspaces] = useState([]);
    const workspaceListRef = useRef(null);
    const token = localStorage.getItem("token");
    const role = localStorage.getItem("role");
    const [role_test, setRole_test] = useState(false);

    const email = localStorage.getItem("email");

    const handleLogout = () => {
        localStorage.removeItem("token");
        localStorage.removeItem("email");
        localStorage.removeItem("role");
        navigate("/");
    };

    const scrollToWorkspaces = () => {
        workspaceListRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    const loadWorkspaces = async (e) => {
        const response = await fetch("http://localhost:8000/home", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ email }),
        });
        const data = await response.json();
        setWorkspaces(data.workspaces);
    };

    useEffect(() => {
        loadWorkspaces();
        if (role) {
            if (role.toLowerCase() == "administrator") {
                setRole_test(true);
            }
        }

        if (!token) {
            navigate("/");

        }
    }, [token, role, navigate]);

    const handleCreateWorkspace = async (e) => {
        e.preventDefault();
        const response = await fetch("http://localhost:8000/new_workspace", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ newWorkspaceName, newWorkspaceDescription, email }),
        });
        const data = await response.json();
        if (response.ok && !data.messageError) {
            setShowModal(false);
            navigate(`/workspace/${data.workspace_id}`);
        }
        else {
            setMessageError(data.messageError);
        }
    };


    return (
        <div className="home-container">
            <div className="background-image"></div>

            <nav className="glass-nav">
                <div className="nav-logo">LabX</div>
                <button onClick={handleLogout} className="logout-btn">
                    <span>Log Out</span>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                        <polyline points="16 17 21 12 16 7"></polyline>
                        <line x1="21" y1="12" x2="9" y2="12"></line>
                    </svg>
                </button>
            </nav>

            <main className="dashboard-content">
                <header className="dashboard-header">
                    <h1>Welcome back, Researcher</h1>
                    <p>Your digital lab and collaborative workspaces await.</p>
                </header>

                <div className="workspace-grid">
                    <div className="create-card" onClick={() => setShowModal(true)}>
                        <div className="add-icon">+</div>
                        <h3>Create New Test Environment</h3>
                        <p>Start a new project or research area</p>
                    </div>

                    <div className="create-card" onClick={scrollToWorkspaces}>
                        <div className="add-icon">
                            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                            </svg>
                        </div>
                        <h3>Manage Workspace</h3>
                        <p>Modify or manage your existing environments</p>
                    </div>

                    <div className={`create-card ${!role_test ? "disabled-card" : ""}`} onClick={() => role_test && navigate("/manageusers")}>
                        <div className="add-icon">
                            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                                <circle cx="9" cy="7" r="4"></circle>
                                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                            </svg>
                        </div>
                        <h3>Manage Users</h3>
                        <p>View and manage researcher permissions</p>
                    </div>

                </div>

                <div className="workspace-list-section" ref={workspaceListRef}>
                    <h2 className="section-title">Your Workspaces</h2>
                    <div className="workspace-list">
                        {workspaces.map((ws, index) => (
                            <div key={index} className="workspace-card">
                                <div className="ws-folder">
                                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                                    </svg>
                                </div>
                                <h3>{ws.name}</h3>
                                <p>{ws.description}</p>
                                <button className="enter-ws" onClick={() => navigate(`/workspace/${ws._id}`)}>Enter Workspace</button>
                            </div>
                        ))}
                    </div>
                </div>
            </main>

            {showModal && (
                <div className="modal-overlay">
                    <div className="modal-card">
                        <h2>Create Workspace</h2>
                        <form onSubmit={handleCreateWorkspace}>
                            <div className="form-group">
                                <label htmlFor="ws-name">Workspace Name</label>
                                <div className="input-wrapper">
                                    <input
                                        type="text"
                                        id="ws-name"
                                        value={newWorkspaceName}
                                        onChange={(e) => setNewWorkspaceName(e.target.value)}
                                        placeholder="e.g. Quantum Research Lab"
                                        required
                                        autoFocus
                                    />
                                </div>
                                <span className="error-message">{messageError}</span>
                            </div>
                            <div className="form-group">
                                <label htmlFor="ws-description">Description</label>
                                <div className="input-wrapper">
                                    <textarea
                                        id="ws-description"
                                        value={newWorkspaceDescription}
                                        onChange={(e) => setNewWorkspaceDescription(e.target.value)}
                                        placeholder="Briefly describe the purpose of this workspace..."
                                        rows="3"
                                    />
                                </div>
                            </div>
                            <div className="modal-actions">
                                <button type="button" className="cancel-btn" onClick={() => setShowModal(false)}>Cancel</button>
                                <button type="submit" className="create-btn">Create</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}

export default Home;
