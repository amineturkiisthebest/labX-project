import { useState } from "react";
import "./login.css";
import { useNavigate } from "react-router-dom";


function Login() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [emailResponse, setEmailResponse] = useState("");
    const [passwordResponse, setPasswordResponse] = useState("");
    const navigate = useNavigate();

    const handleLoginSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        let token = null;

        // Mocking a login request
        const response = await fetch("http://localhost:8000/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ email, password }),
        });
        const data = await response.json();
        if (data.emailError)
            setEmailResponse(data.emailError);
        if (data.passwordError)
            setPasswordResponse(data.passwordError);
        if (data.access_token) {
            localStorage.setItem("email", email);
            localStorage.setItem("token", data.access_token);
            localStorage.setItem("role", data.role);
            setLoading(false);
            token = localStorage.getItem("token");
            navigate("/home");
        }

    }
    const handleSignUpSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        navigate("/signup");
    }


    return (
        <div className="app-container">
            <div className="background-image"></div>

            <div className="login-card">
                <div className="login-header">
                    <h1>LabX</h1>
                    <p>Welcome back! Please enter your details.</p>
                </div>

                <form onSubmit={handleLoginSubmit}>
                    <div className="form-group">
                        <label htmlFor="email">Email Address</label>
                        <div className="input-wrapper">
                            <input
                                type="email"
                                id="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                            />
                        </div>
                        <span className="error-message">{emailResponse}</span>
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
                            />
                        </div>
                        <span className="error-message">{passwordResponse}</span>
                    </div>

                    <div className="form-actions">
                        <label className="remember-me">
                            <input type="checkbox" />
                            <span>Remember me</span>
                        </label>
                    </div>

                    <button type="submit" className="login-button" disabled={loading}>
                        {loading ? "Signing in..." : "Sign In"}
                    </button>
                </form>
                <div className="login-footer">
                    <p>Don't have an account? <a onClick={handleSignUpSubmit} >Sign up for free</a></p>
                </div>
            </div>
        </div>
    );
};
export default Login;
