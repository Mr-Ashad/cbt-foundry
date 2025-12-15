// src/components/StartForm.jsx
import React, { useState } from 'react';

function StartForm({ onSubmit, disabled }) {
    const [userIntent, setUserIntent] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!userIntent.trim() || disabled) return;
        onSubmit(userIntent.trim());
    };

    return (
        <div className="antialiased max-w-3xl w-full p-6 bg-white rounded-xl shadow-lg border border-gray-200 font-sans">
            <h2 className="text-2xl font-semibold text-gray-800 mb-4">
                Define the Protocol Goal
            </h2>

            <form onSubmit={handleSubmit} className="space-y-4">
                <textarea
                    className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 transition"
                    rows="4"
                    placeholder="E.g., Create a detailed CBT protocol for a patient struggling with severe social anxiety..."
                    value={userIntent}
                    onChange={(e) => setUserIntent(e.target.value)}
                    disabled={disabled}
                    required
                />

                <button
                    type="submit"
                    disabled={disabled}
                    className={`py-2.5 px-5 rounded-2xl text-white font-bold-md transition ${
                        disabled
                            ? 'bg-green-300 cursor-not-allowed'
                            : 'bg-green-600 hover:bg-green-700 focus:ring-2 focus:ring-indigo-500'
                    }`}
                >
                    {disabled ? 'Workflow Starting…' : 'Start Protocol Generation'}
                </button>

                {disabled && (
                    <p className="text-sm text-gray-500">
                        Initializing workflow…
                    </p>
                )}
            </form>
        </div>
    );
}

export default StartForm;
