import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import "./Testflow.css";

function Testflow() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [workspace, setWorkspace] = useState(null);
    const [isTesting, setIsTesting] = useState(false);
    const [logs, setLogs] = useState([]);
    const [progress, setProgress] = useState(0);
    const [showOptions, setShowOptions] = useState(false);
    const [selectedFrequency, setSelectedFrequency] = useState("once");
    const [hasClickedStart, setHasClickedStart] = useState(false);
    const [hasStoppedPackets, setHasStoppedPackets] = useState(false);
    const [testMode, setTestMode] = useState(null);
    const [isLoadingProtocol, setIsLoadingProtocol] = useState(false);
    const [showDiameterOptions, setShowDiameterOptions] = useState(false);
    const [selectedDiameterMsg, setSelectedDiameterMsg] = useState("CER/CEA");

    useEffect(() => {
        // Simulating a fetch of the workspace details
        const fetchWorkspace = async () => {
            try {
                // In a real scenario, you'd fetch the workspace info using the id
                setTimeout(() => {
                    setWorkspace({
                        name: "Test Environment Call Flow",
                        description: "Validating configuration and executing simulated packet transmission for workspace: " + id
                    });
                }, 500);
            } catch (err) {
                console.error(err);
            }
        };
        fetchWorkspace();
    }, [id]);

    const stopPackets = async () => {
        const response = await fetch(`http://localhost:8000/stop_packets/${id}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
        });
        const data = await response.json();
        console.log(data.response)
        setHasStoppedPackets(true);
    }

    const executeTest = async () => {
        const response = await fetch(`http://localhost:8000/test_flow/${id}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                frequency: selectedFrequency
            })
        });
        const data = await response.json();
        console.log(data.response)
        setTestMode('icmp');
        setHasClickedStart(true);
        setHasStoppedPackets(false);
        setShowOptions(false);
        setIsTesting(true);
        setLogs([]);
        setProgress(0);

        let packetLogs = [];
        if (Array.isArray(data.response)) {
            packetLogs = data.response.map(resp => ({
                type: 'packet',
                status: resp.response ? 'success' : 'error',
                destination_ip: resp.destination_ip,
                label: resp.label || 'Unknown',
                packet: resp.packet,
                response: resp.response
            }));
            if (packetLogs.length === 0) {
                packetLogs = [{ type: 'text', message: "No packet transmissions required." }];
            }
        } else {
            packetLogs = [{ type: 'text', message: `Packet transmission result: ${data.response}` }];
        }

        const simulatedLogs = [
            { type: 'text', message: `Initializing test environment (Frequency: ${selectedFrequency})...` },
            { type: 'text', message: "Loading workspace configuration..." },
            { type: 'text', message: "Establishing connection to backend services..." },
            { type: 'text', message: "Sending initial sync packets..." },
            { type: 'text', message: "Validating node interfaces..." },
            ...packetLogs,
            { type: 'text', message: "Analyzing response latency..." },
            { type: 'text', message: "Verifying security protocols..." },
            { type: 'text', message: "Test completed successfully." }
        ];

        let currentLogIndex = 0;
        const interval = setInterval(() => {
            if (currentLogIndex < simulatedLogs.length) {
                setLogs(prev => [...prev, simulatedLogs[currentLogIndex]]);
                setProgress(((currentLogIndex + 1) / simulatedLogs.length) * 100);
                currentLogIndex++;
            } else {
                clearInterval(interval);
                setIsTesting(false);
            }
        }, 800);
    };

    const export_pcap = async () => {
        const response = await fetch(`http://localhost:8000/save_pcap/${id}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
        });
        const data = await response.json();
        console.log(data.message)
    };

    const checkDiamterConfig = async () => {
        setIsLoadingProtocol(true);
        let data;
        try {
            const response = await fetch(`http://localhost:8000/check_diameter_config/${id}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
            });
            data = await response.json();
        } catch (error) {
            console.error(error);
            setIsLoadingProtocol(false);
            return;
        }
        setIsLoadingProtocol(false);
        if (data.response === "Diameter configuration found") {
            setShowDiameterOptions(true);
        }
        else {
            executeTestProtocol();
        }
    }

    const executeTestProtocol = async (diameterMsg = null) => {
        setShowDiameterOptions(false);
        setIsLoadingProtocol(true);
        let data;
        const bodyData = { frequency: selectedFrequency };
        if (typeof diameterMsg === 'string') {
            bodyData.diameter_message = diameterMsg;
            try {
                const response = await fetch(`http://localhost:8000/test_flow_with_protocol_diameter/${id}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(bodyData)
                });
                data = await response.json();
                console.log(data.response)
            } catch (error) {
                console.error(error);
                setIsLoadingProtocol(false);
                return;
            }
        }
        else {
            try {
                const response = await fetch(`http://localhost:8000/test_flow_with_protocol/${id}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(bodyData)
                });
                data = await response.json();
            } catch (error) {
                console.error(error);
                setIsLoadingProtocol(false);
                return;
            }
        }
        setIsLoadingProtocol(false);
        console.log(data.response)
        setTestMode('protocol');
        setHasClickedStart(true);
        setHasStoppedPackets(false);
        setShowOptions(false);
        setIsTesting(true);
        setLogs([]);
        setProgress(0);

        let packetLogs = [];
        if (Array.isArray(data.response)) {
            packetLogs = data.response.map(resp => ({
                type: 'packet',
                status: resp.response ? 'success' : 'error',
                destination_ip: resp.destination_ip,
                label: resp.label || 'Unknown',
                status_code: resp.status_code,
                http_version: resp.http_version,
                body: resp.body
            }));
            if (packetLogs.length === 0) {
                packetLogs = [{ type: 'text', message: "No http2 packet transmissions found." }];
            }
        } else {
            packetLogs = [{ type: 'text', message: `Packet transmission result: ${data.response}` }];
        }

        const simulatedLogs = [
            { type: 'text', message: `Initializing test environment (Frequency: ${selectedFrequency})...` },
            { type: 'text', message: "Loading workspace configuration..." },
            { type: 'text', message: "Establishing connection to backend services..." },
            { type: 'text', message: "Sending initial sync packets..." },
            { type: 'text', message: "Validating node interfaces..." },
            ...packetLogs,
            { type: 'text', message: "Analyzing response latency..." },
            { type: 'text', message: "Verifying security protocols..." },
            { type: 'text', message: "Test completed successfully." }
        ];

        let currentLogIndex = 0;
        const interval = setInterval(() => {
            if (currentLogIndex < simulatedLogs.length) {
                setLogs(prev => [...prev, simulatedLogs[currentLogIndex]]);
                setProgress(((currentLogIndex + 1) / simulatedLogs.length) * 100);
                currentLogIndex++;
            } else {
                clearInterval(interval);
                setIsTesting(false);
            }
        }, 800);
    };
    return (
        <div className="testflow-container">
            <div className="testflow-bg"></div>

            <nav className="testflow-nav">
                <div className="nav-brand" onClick={() => navigate('/home')}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M19 12H5"></path>
                        <polyline points="12 19 5 12 12 5"></polyline>
                    </svg>
                    <span>Back to Home</span>
                </div>
                <div className="nav-title">Call Flow Testing</div>
            </nav>

            <main className="testflow-main">
                <header className="testflow-header">
                    <h1>{workspace ? workspace.name : "Loading Workspace..."}</h1>
                    <p>{workspace ? workspace.description : "Please wait..."}</p>
                </header>

                <div className="test-dashboard">
                    <div className="controls-panel glass-panel">
                        <h2>Test Controls</h2>
                        <p>Initiate packet transmission and validate your call flow configuration. This action will simulate traffic across all configured nodes.</p>

                        {showDiameterOptions ? (
                            <div className="frequency-options diameter-options">
                                <h3>Diameter Configuration Detected</h3>
                                <p className="diameter-desc">It seems that you have configured Diameter connections. What kind of Diameter message do you want to test?</p>
                                <div className="radio-group">
                                    <label>
                                        <input type="radio" value="CER/CEA" checked={selectedDiameterMsg === "CER/CEA"} onChange={(e) => setSelectedDiameterMsg(e.target.value)} />
                                        Capabilities-Exchange Request/Answer (CER/CEA)
                                    </label>
                                    <label>
                                        <input type="radio" value="DWR/DWA" checked={selectedDiameterMsg === "DWR/DWA"} onChange={(e) => setSelectedDiameterMsg(e.target.value)} />
                                        Device-Watchdog Request/Answer (DWR/DWA)
                                    </label>
                                    <label>
                                        <input type="radio" value="RAR/RAA" checked={selectedDiameterMsg === "RAR/RAA"} onChange={(e) => setSelectedDiameterMsg(e.target.value)} />
                                        Re-Auth Request/Answer (RAR/RAA)
                                    </label>
                                </div>
                                <div className="options-actions">
                                    <button className="confirm-btn" onClick={() => executeTestProtocol(selectedDiameterMsg)} disabled={isLoadingProtocol}>Start Protocol Test</button>
                                    <button className="cancel-btn" onClick={() => setShowDiameterOptions(false)} disabled={isLoadingProtocol}>Back</button>
                                </div>
                            </div>
                        ) : showOptions ? (
                            <div className="frequency-options">
                                <h3>Select Transmission Frequency</h3>
                                <div className="radio-group">
                                    <label>
                                        <input type="radio" value="once" checked={selectedFrequency === "once"} onChange={(e) => setSelectedFrequency(e.target.value)} />
                                        Once
                                    </label>
                                    <label>
                                        <input type="radio" value="10s" checked={selectedFrequency === "10s"} onChange={(e) => setSelectedFrequency(e.target.value)} />
                                        Every 10 Seconds
                                    </label>
                                    <label>
                                        <input type="radio" value="20s" checked={selectedFrequency === "20s"} onChange={(e) => setSelectedFrequency(e.target.value)} />
                                        Every 20 Seconds
                                    </label>
                                    <label>
                                        <input type="radio" value="30s" checked={selectedFrequency === "30s"} onChange={(e) => setSelectedFrequency(e.target.value)} />
                                        Every 30 Seconds
                                    </label>
                                </div>
                                <div className="options-actions">
                                    <button className="confirm-btn" onClick={executeTest} disabled={isLoadingProtocol}>Connectivity mode (icmp)</button>
                                    <button className="confirm-btn" style={{ minWidth: '180px' }} onClick={() => checkDiamterConfig()} disabled={isLoadingProtocol}>
                                        {isLoadingProtocol ? (
                                            <span style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'center' }}>
                                                <div className="spinner" style={{ width: '16px', height: '16px', borderWidth: '2px', display: 'inline-block', margin: 0 }}></div>
                                                Sending...
                                            </span>
                                        ) : (
                                            "Functional protocol mode"
                                        )}
                                    </button>
                                    <button className="cancel-btn" onClick={() => setShowOptions(false)} disabled={isLoadingProtocol}>Cancel</button>
                                </div>
                            </div>
                        ) : (
                            <button
                                className={`action-btn ${isTesting ? 'testing' : ''}`}
                                onClick={() => { setShowOptions(true); setHasClickedStart(false); setTestMode(null); }}
                                disabled={isTesting}
                            >
                                {isTesting ? (
                                    <>
                                        <div className="spinner"></div>
                                        Testing in Progress...
                                    </>
                                ) : (
                                    "Start Call Flow Test"
                                )}
                            </button>
                        )}

                        {hasClickedStart && (
                            <>
                                {testMode === 'icmp' && (
                                    <button className="export-pcap-btn pop-up-anim" onClick={() => export_pcap()}>
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                            <polyline points="7 10 12 15 17 10"></polyline>
                                            <line x1="12" y1="15" x2="12" y2="3"></line>
                                        </svg>
                                        Save Packets as PCAP
                                    </button>
                                )}
                                {selectedFrequency !== "once" && !hasStoppedPackets && (
                                    <button
                                        className="export-pcap-btn pop-up-anim"
                                        style={{ background: '#ef4444', color: 'white', marginTop: '10px', boxShadow: '0 4px 10px rgba(239, 68, 68, 0.3)' }}
                                        onClick={stopPackets}
                                    >
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                                        </svg>
                                        Stop Sending Packets
                                    </button>
                                )}
                            </>
                        )}

                        <div className="progress-container">
                            <div className="progress-bar" style={{ width: `${progress}%` }}></div>
                        </div>
                        <div className="status-text">
                            {progress === 100 ? "Test Completed" : isTesting ? `${Math.round(progress)}% Complete` : "Ready to test"}
                        </div>
                    </div>

                    <div className="terminal-panel glass-panel">
                        <div className="terminal-header">
                            <div className="window-controls">
                                <span></span><span></span><span></span>
                            </div>
                            <div className="terminal-title">Transmission Logs - bash</div>
                        </div>
                        <div className="terminal-body">
                            {logs.length === 0 && !isTesting ? (
                                <div className="terminal-placeholder">Awaiting test initiation...</div>
                            ) : (
                                logs.map((log, idx) => {
                                    if (!log) return null;
                                    if (log.type === "text") {
                                        return (
                                            <div key={idx} className="log-entry">
                                                <span className="log-timestamp">[{new Date().toLocaleTimeString()}]</span>
                                                <span className="log-message">
                                                    {log.message}
                                                </span>
                                            </div>
                                        );
                                    } else if (log.type === "packet") {
                                        return (
                                            <div key={idx} className="log-entry packet-entry">
                                                <div className="packet-header">
                                                    <span className="log-timestamp">[{new Date().toLocaleTimeString()}]</span>
                                                    <span className={`packet-status ${log.status}`}>[{log.status.toUpperCase()}]</span>
                                                    <span className="packet-dest">To: {log.destination_ip}</span>
                                                    <span className="packet-label">({log.label})</span>
                                                </div>
                                                <div className="packet-details">
                                                    <div className="packet-req"><span className="packet-tag req">REQ</span> {log.packet}</div>
                                                    <div className="packet-res"><span className="packet-tag res">RES</span> {log.response || "No response received"}</div>
                                                </div>
                                            </div>
                                        );
                                    }
                                    return null;
                                })
                            )}
                            {isTesting && <div className="typing-indicator">_</div>}
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}

export default Testflow;
