import { BrowserRouter, Routes, Route } from "react-router-dom";
import Login from "./Login";
import Signup from "./Signup";
import Home from "./Home";
import Workspace from "./Workspace";
import ManageUsers from "./Manageusers";
import Testflow from "./Testflow";

function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/signup" element={<Signup />} />
                <Route path="/home" element={<Home />} />
                <Route path="/" element={<Login />} />
                <Route path="/workspace/:id" element={<Workspace />} />
                <Route path="/manageusers" element={<ManageUsers />} />
                <Route path="/Testflow/:id" element={<Testflow />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;