(require 'mew-search)

(setq mew-prog-mewgrep "/home/masm/bin/mewgrep.py")
(setq mew-prog-mewgrep-make-index "/home/masm/bin/mewgrep-make-index.py")

(add-to-list 'mew-search-switch
	     `(mewgrep					; key
	       "Mewgrep"				; name
	       ,mew-prog-mewgrep			; prog
	       mew-search-with-mewgrep			; func-search
	       mew-search-virtual-with-mewgrep		; func-virtual
	       nil					; func-index-folder
	       mew-mewgrep-index-all			; func-index-all
	       mew-pick-canonicalize-pattern-mewgrep	; func-canonicalize-pattern
	       nil nil))

(defun mew-search-mewgrep (pattern paths)
  (setq pattern (mew-cs-encode-string pattern 'utf-8))
  (let* ((ent (mew-search-get-ent mew-search-method))
	 (prog (mew-search-get-prog ent))
	 (args nil))
    (setq args (cons "-q" (cons pattern args)))
    (dolist (path paths)
	    (setq args (cons "-f" (cons path args))))
    (setq args (cons "-r" (cons (expand-file-name mew-mail-path) args)))
    (mew-plet
     (mew-alet
      (apply 'call-process prog nil t nil args)))))

(defun mew-search-with-mewgrep (pattern folder &optional _dummy)
  (let* ((folders (list (string-remove-prefix "+" folder)))
	 msgs)
    (with-temp-buffer
      (mew-set-buffer-multibyte t)
      (mew-search-mewgrep pattern folders)
      (goto-char (point-min))
      (while (re-search-forward mew-regex-message-files5 nil t)
	(setq msgs (cons (mew-match-string 1) msgs))
	(forward-line))
      (setq msgs (nreverse msgs))
      (setq msgs (sort (mapcar 'string-to-number msgs) '<))
      (mapcar 'number-to-string msgs)))
  )

(defun mew-search-virtual-with-mewgrep (pattern flds &optional _dummy)
  (let* ((folders (mapcar (lambda (fld) (string-remove-prefix "+" fld)) flds))
	 (regex (concat "\\(.*\\)/" "\\([0-9]+\\)"))
	 (file (mew-make-temp-name))
	 (prev "") (rttl 0)
	 crnt)
    (mew-search-mewgrep pattern folders)
    (goto-char (point-min))
    (while (not (eobp))
      (when (looking-at regex)
	(setq rttl (1+ rttl))
	(setq crnt (match-string 1))
	(delete-region (match-beginning 0) (match-beginning 2))
	(when (not (string= crnt prev))
	  (beginning-of-line)
	  (insert "CD:" mew-folder-local crnt "\n"))
	(setq prev crnt)
	(forward-line)))
    (mew-frwlet mew-cs-text-for-read mew-cs-text-for-write
      (write-region (point-min) (point-max) file nil 'no-msg))
    (list file rttl)))

(defun mew-mewgrep-index-all ()
  "Make mewgrep index for all folders."
  (interactive)
  (start-process mew-prog-mewgrep-make-index nil mew-prog-mewgrep-make-index)
  (message "Mewgrep indexing for all folders in background..."))

(defun mew-pick-canonicalize-pattern-mewgrep (pattern)
  (let ((mew-inherit-pick-omit-and t)
	(tokens (mew-pick-parse (mew-pick-lex pattern)))
	token
	ret)
    (while tokens
      (setq token (car tokens))
      (setq tokens (cdr tokens))
      (if (eq token 'not)
	  (if (stringp (car tokens))
	      (progn
		(setq ret (cons (concat "not " (car tokens)) ret))
		(setq tokens (cdr tokens)))
	    nil) ;; xxx
	(setq ret (cons token ret))))
    (mapconcat
     'mew-pick-native-text-mewgrep
     (nreverse ret)
     " ")))

(defun mew-pick-native-text-mewgrep (token)
  (mew-pick-native-text "mew-pick-pattern-mewgrep-" token))

(defun mew-pick-pattern-mewgrep-and   (_sym) "and")
(defun mew-pick-pattern-mewgrep-or    (_sym) "or")
(defun mew-pick-pattern-mewgrep-open  (_sym) "(")
(defun mew-pick-pattern-mewgrep-close (_sym) ")")
(defun mew-pick-pattern-mewgrep-not   (_sym) "not")
(defun mew-pick-pattern-mewgrep-key   (key) key)
(defun mew-pick-pattern-mewgrep-kyvl  (kyvl)
  (let ((op (nth 0 kyvl)))
    (error "'%s' is not supported" op)))

(let ((methods (mew-search-get-list 'mew-search-get-key)))
  (if (memq 'mewgrep methods)
      (setq mew-search-method 'mewgrep)))

(provide 'mew-mewgrep)
