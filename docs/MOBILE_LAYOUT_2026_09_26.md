# Mobile layout correction

The staging screenshots show oversized actions and a roster caption broken into individual letters. Shared phone rules combined column flex direction with a 10rem child basis, turning a width intention into roughly 160px button height. The mobile table switched to block layout without switching its caption.

Actions now use content height with a 44px minimum target; roster actions use a wrapping grid. Mobile management rules align with the shared 650px breakpoint. Captions are full-width blocks, cell line breaks no longer create empty grid rows, and screen-reader-only labels have an actual hiding utility. Latest location evidence remains visible; historical verification readings are available through a keyboard-operable native disclosure.

Manual acceptance outstanding: check login, participant tickets/tasks/communities, organizer events/members/attendance and platform forms at 360px, 390px, 650px, tablet and desktop widths. Check long labels, keyboard focus, zoom, expanded evidence and bottom-navigation clearance. No deployed visual verification is claimed.
