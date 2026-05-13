import * as React from 'react';
declare const MARK = "__rc_react_root__";
type RootType = {
    render: (node: React.ReactNode) => void;
    unmount: () => void;
};
type ContainerType = (Element | DocumentFragment) & {
    [MARK]?: RootType;
};
export declare function render(node: React.ReactElement, container: ContainerType): Promise<void>;
export declare function unmount(container: ContainerType): Promise<void>;
export {};
