// src/components/DraftViewer.jsx
import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';

function DraftViewer({
    draft,
    onDraftChange,
    initialDecision,
    workflowStatus
}) {
    const [isEditMode, setIsEditMode] = useState(false);

    const isHumanReview = workflowStatus === 'AWAITING_HUMAN_REVIEW';

    // 🔑 HARD GUARANTEE: exit edit mode when workflow resumes
    useEffect(() => {
        if (!isHumanReview && isEditMode) {
            setIsEditMode(false);
        }
    }, [isHumanReview, isEditMode]);

    // 🔑 SINGLE SOURCE OF TRUTH
    const contentToDisplay = isHumanReview && isEditMode
        ? (initialDecision ?? '')
        : (draft ??
            "--- Protocol Draft Awaiting Generation ---\n\n(The AI will generate the initial protocol draft here.)"
          );

    return (
        <div className="flex flex-col p-6 bg-white rounded-xl shadow-lg border border-gray-200 min-h-[114.3vh] max-h-[114.3vh] font-sans">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-semibold text-gray-800">
                    Current Protocol Draft
                </h2>

                {isHumanReview && (
                    <button
                        onClick={() => setIsEditMode(prev => !prev)}
                        className={`px-4 py-2 rounded-lg font-medium transition
                            ${isEditMode
                                ? 'bg-gray-700 text-white hover:bg-gray-800'
                                : 'bg-blue-400 text-white hover:bg-blue-500'}`}
                    >
                        {isEditMode ? 'Done Editing' : 'Edit Draft'}
                    </button>
                )}
            </div>

            {/* EDIT MODE */}
            {isHumanReview && isEditMode ? (
                <>
                    <textarea
                        className="flex-1 w-full p-4 border rounded-lg font-sans text-base leading-relaxed
                                max-h-[calc(100vh-10px)] overflow-y-auto
                                border-pink-500 bg-pink-50
                                focus:ring-pink-500 focus:border-pink-500"
                        value={contentToDisplay}
                        onChange={(e) => onDraftChange(e.target.value)}
                        placeholder="Edit the protocol draft here..."
                    />
                    <p className="mt-2 text-pink-700 font-medium">
                        EDIT MODE: Make changes, then click <b>Done Editing</b>.
                    </p>
                </>
            ) : (
                /* READ-ONLY MARKDOWN VIEW */
                <div className=" flex-1 w-full p-4 bg-gray-50 border border-gray-300 rounded-lg
                                text-gray-800  overflow-y-auto">
                    <div className="-full leading-relaxed max-h-[calc(100vh-20px)] prose max-w-none w-full font-sans text-base leading-relaxed">
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypeRaw]}
                            remarkRehypeOptions={{ allowDangerousHtml: true }}
                        >
                            {contentToDisplay}
                        </ReactMarkdown>
                    </div>
                </div>
            )}
        </div>
    );
}

export default DraftViewer;
