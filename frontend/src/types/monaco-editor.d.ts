declare module 'monaco-editor' {
  export namespace editor {
    interface IStandaloneCodeEditor {
      getModel(): any;
      setModel(model: any): void;
      setValue(value: string): void;
      getValue(): string;
      getAction(id: string): any;
      addAction(action: { id: string; label: string; keybindings?: number[]; run: (editor: IStandaloneCodeEditor) => void }): void;
      trigger(source: string, handlerId: string, payload: any): void;
      onDidChangeModelContent(listener: (e: any) => void): any;
      dispose(): void;
    }
    function createModel(value: string, language: string, uri?: any): any;
    interface IEditorOptions {
      [key: string]: any;
    }
  }
  export namespace languages {
    function registerCompletionItemProvider(language: string, provider: any): void;
    function setLanguageConfiguration(language: string, configuration: any): void;
    namespace json {
      const jsonDefaults: {
        setDiagnosticsOptions(options: any): void;
      };
    }
  }
  export const KeyMod: { CtrlCmd: number; Shift: number; Alt: number };
  export const KeyCode: { [key: string]: number };
  export namespace Uri {
    function parse(value: string): any;
  }
}
