from App import App
import sys
import os
import tkinter.messagebox


if __name__ == "__main__":
    app = App()

    def confirmExit():
        if tkinter.messagebox.askokcancel('Quit', 'Are you sure you want to exit?'):
            # Delete all HTML files in the current directory
            for file in os.listdir('.'):
                if file.endswith('.html'):
                    try:
                        os.remove(file)
                    except Exception as e:
                        print(f"Error deleting file {file}: {e}")
            
            # Exit the application
            sys.exit()

    
    app.protocol('WM_DELETE_WINDOW', confirmExit)  
    app.mainloop()