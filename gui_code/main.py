from App import App
import sys
import tkinter.messagebox


if __name__ == "__main__":
    app = App()
    def confirmExit():
        if tkinter.messagebox.askokcancel('Quit', 'Are you sure you want to exit?'):
            sys.exit()
    app.protocol('WM_DELETE_WINDOW', confirmExit)  
    app.mainloop()