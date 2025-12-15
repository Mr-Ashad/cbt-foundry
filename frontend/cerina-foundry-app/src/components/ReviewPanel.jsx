// src/components/ReviewPanel.jsx
import React from 'react';

/**
 * Component displayed when the workflow is AWAITING_HUMAN_REVIEW.
 * It shows the agent's final critique before the HIL step.
 * * @param {string} critiqueNotes - The agent's notes on why it paused.
 * @param {boolean} loading - Flag to disable button during resume call.
 * @param {function} onApprove - Handler to resume the workflow.
 */
function ReviewPanel({ critique, loading, onApprove, onRevise }) {
    return (
        <div className="mx-auto p-6 bg-yellow-50 rounded-2xl shadow-lg border border-yellow-300 font-sans">
            <h3 className="text-2xl font-bold mb-3">
                Human-in-the-Loop Interruption
            </h3>

            <p className="text-sm text-gray-700 mb-4">
                The agent has reached a key review stage before finalization. Please review the draft above and proceed.
            </p>

            <div className="flex space-x-4 mt-5">
                <button
                    onClick={onRevise}
                    className={`w-1/2 py-3 px-4 rounded-xl text-white font-bold transition duration-300 ${
                        loading
                            ? 'bg-orange-300 cursor-not-allowed'
                            : 'bg-orange-400 hover:bg-orange-600 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2'
                    }`}
                    disabled={loading}
                >
                    {loading ? 'Submitting...' : '📝 Request Revision'}
                </button>
                <button
                    onClick={onApprove}
                    className={`w-1/2 py-3 px-4 rounded-xl text-white font-bold transition duration-300 ${
                        loading
                            ? 'bg-green-300 cursor-not-allowed'
                            : 'bg-green-400 hover:bg-green-600 focus:outline-none focus:ring-4 focus:ring-green-500 focus:ring-offset-2'
                    }`}
                    disabled={loading}
                >
                    {loading ? 'Finalizing...' : '✅ Approve & Finalize'}
                </button>
            </div>
        </div>
    );
}

export default ReviewPanel;