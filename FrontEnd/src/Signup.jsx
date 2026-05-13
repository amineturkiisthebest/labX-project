import { useState } from "react";
import "./signup.css";
import { useNavigate } from "react-router-dom";

function Signup() {
    const [username, setUsername] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [role, setRole] = useState("NormalUser");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [emailError, setEmailError] = useState("");
    const [usernameError, setUsernameError] = useState("");

    const navigate = useNavigate();

    const handleSignupSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);

        try {
            const response = await fetch("http://localhost:8000/signup", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ username, email, password, role }),
            });

            const data = await response.json();

            if (response.ok && !data.emailError && !data.usernameError) {
                console.log("Signup Successful:", data);
                navigate("/"); // Redirect to login after successful signup
            } else {
                setEmailError(data.emailError);
                setUsernameError(data.usernameError);
            }
        } catch (err) {
            setError("An error occurred. Please try again.");
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="app-container">
            <div className="background-image"></div>

            <div className="signup-card">
                <div className="signup-header">
                    <h1>LabX</h1>
                    <p>Create your account to get started.</p>
                </div>

                <form onSubmit={handleSignupSubmit}>
                    <div className="form-group">
                        <label htmlFor="username">Username</label>
                        <div className="input-wrapper">
                            <input
                                type="text"
                                id="username"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                                placeholder="Choose a username"
                            />
                        </div>
                        <span className="error-message">{usernameError}</span>
                    </div>

                    <div className="form-group">
                        <label htmlFor="email">Email Address</label>
                        <div className="input-wrapper">
                            <input
                                type="email"
                                id="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                placeholder="Enter your email"
                            />
                        </div>
                        <span className="error-message">{emailError}</span>
                    </div>

                    <div className="form-group">
                        <label htmlFor="password">Password</label>
                        <div className="input-wrapper">
                            <input
                                type="password"
                                id="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                placeholder="Create a password"
                            />
                        </div>
                    </div>


                    {error && <span className="error-message" style={{ marginBottom: '15px' }}>{error}</span>}

                    <button type="submit" className="signup-button" disabled={loading}>
                        {loading ? "Creating Account..." : "Sign Up"}
                    </button>
                </form>

                <div className="signup-footer">
                    <p>Already have an account? <a onClick={() => navigate("/")} style={{ cursor: 'pointer' }}>Sign In</a></p>
                </div>
            </div>
        </div>
    );
}


export default Signup;
