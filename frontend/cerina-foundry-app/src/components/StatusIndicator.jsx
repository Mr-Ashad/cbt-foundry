// src/components/StatusIndicator.jsx
import React from 'react';

/**
 * Maps the workflow status to a visually distinct color and icon.
 */
const statusMap = {
    IDLE: { text: 'Idle', color: 'bg-blue-100 text-blue-700 border-blue-400' },
    RUNNING: { text: 'Workflow Running...', color: 'bg-yellow-100 text-yellow-700 border-yellow-400'},
    AWAITING_HUMAN_REVIEW: { text: 'Human Approval Required', color: 'bg-pink-100 text-pink-700 border-pink-400' },
    COMPLETED: { text: 'Protocol Finalized', color: 'bg-green-100 text-green-700 border-green-400' },
    FAILED: { text: 'Error', color: 'bg-red-100 text-red-700 border-red-400' },
};

function StatusIndicator({ status, loading, error, threadId }) {
    const { text, color, icon } = statusMap[status] || statusMap['IDLE'];

    return (
        <div className={`p-2 rounded-lg border shadow-sm ${color} transition-colors duration-300 font-sans antialiased`}>
            <div className="flex justify-between items-center">
                <p className="text-xl font-bold flex items-center">
                    {text}
                </p>
                {threadId && (
                    <p className="text-sm font-mono opacity-75">
                        Thread ID: {threadId.substring(0, 8)}...
                    </p>
                )}
            </div>
            {loading && (
                <p className="text-sm mt-2 opacity-80">
                    Communicating with backend...
                </p>
            )}
            {error && (
                <p className="h-[100px] overflow-y-auto text-sm mt-2 font-semibold">
                    System Error: {error}
                </p>
            )}
        </div>
    );
}

export default StatusIndicator;